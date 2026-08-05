from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import urlparse

from .portal_assistant import (
    PortalAssistantError,
    PortalPrefillPlan,
    _current_page,
    _inject_manual_helper,
    _interactive_manual_session,
    _safe_screenshot,
    prefill_current_page,
)


def _portal_cfg(settings: dict[str, Any]) -> dict[str, Any]:
    raw = settings.get("portal_assistant", {})
    return raw if isinstance(raw, dict) else {}


def _cdp_url(cfg: dict[str, Any]) -> str:
    return str(cfg.get("cdp_url", "http://127.0.0.1:9222")).rstrip("/")


def _cdp_ready(url: str, timeout: float = 1.0) -> bool:
    endpoint = f"{url}/json/version"
    try:
        with urllib.request.urlopen(endpoint, timeout=timeout) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, ValueError):
        return False


def _wait_cdp(url: str, timeout_seconds: float = 15.0) -> bool:
    deadline = time.monotonic() + max(1.0, timeout_seconds)
    while time.monotonic() < deadline:
        if _cdp_ready(url):
            return True
        time.sleep(0.35)
    return False


def _candidate_browser_paths(cfg: dict[str, Any]) -> list[Path]:
    configured = str(cfg.get("executable_path", "")).strip()
    paths: list[Path] = []
    if configured:
        paths.append(Path(configured).expanduser())

    for command in ("chrome.exe", "chrome", "msedge.exe", "msedge"):
        found = shutil.which(command)
        if found:
            paths.append(Path(found))

    local = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("PROGRAMFILES", "")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", "")
    for root, relative in (
        (local, r"Google\Chrome\Application\chrome.exe"),
        (program_files, r"Google\Chrome\Application\chrome.exe"),
        (program_files_x86, r"Google\Chrome\Application\chrome.exe"),
        (program_files, r"Microsoft\Edge\Application\msedge.exe"),
        (program_files_x86, r"Microsoft\Edge\Application\msedge.exe"),
    ):
        if root:
            paths.append(Path(root) / relative)

    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).lower()
        if key not in seen:
            unique.append(path)
            seen.add(key)
    return unique


def find_external_browser(settings: dict[str, Any]) -> Path:
    cfg = _portal_cfg(settings)
    for path in _candidate_browser_paths(cfg):
        if path.exists() and path.is_file():
            return path.resolve()
    raise PortalAssistantError(
        "Google Chrome/Microsoft Edge tidak ditemukan. Isi portal_assistant.executable_path di config/settings.json."
    )


def launch_portal_login_browser(
    settings: dict[str, Any],
    *,
    initial_url: str | None = None,
) -> dict[str, Any]:
    """Launch a normal Chrome/Edge process with a dedicated persistent profile.

    The process is not launched by Playwright, so Google login is performed in a
    normal browser session. Playwright attaches later through the local CDP port.
    """
    cfg = _portal_cfg(settings)
    cdp_url = _cdp_url(cfg)
    if _cdp_ready(cdp_url):
        return {
            "status": "ALREADY_RUNNING",
            "cdp_url": cdp_url,
            "user_data_dir": str(
                Path(str(cfg.get("external_user_data_dir", "data/browser_profile_external"))).resolve()
            ),
        }

    parsed = urlparse(cdp_url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise PortalAssistantError("cdp_url harus menggunakan alamat lokal 127.0.0.1/localhost")
    port = parsed.port or 9222
    executable = find_external_browser(settings)
    user_data_dir = Path(
        str(cfg.get("external_user_data_dir", "data/browser_profile_external"))
    ).resolve()
    user_data_dir.mkdir(parents=True, exist_ok=True)
    url = initial_url or str(
        cfg.get("login_url", "https://www.kitalulus.com/")
    ).strip()

    command = [
        str(executable),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window",
        url,
    ]
    kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        detached_process = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        new_process_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        kwargs["creationflags"] = detached_process | new_process_group
    else:
        kwargs["start_new_session"] = True

    try:
        subprocess.Popen(command, **kwargs)
    except OSError as exc:
        raise PortalAssistantError(f"Browser gagal dibuka: {exc}") from exc

    if not _wait_cdp(cdp_url, float(cfg.get("cdp_start_timeout_seconds", 15))):
        raise PortalAssistantError(
            "Browser terbuka tetapi koneksi antrean belum siap. Tutup browser profil KarirLog, lalu jalankan portal_login.bat lagi."
        )
    return {
        "status": "LAUNCHED",
        "cdp_url": cdp_url,
        "browser": str(executable),
        "user_data_dir": str(user_data_dir),
        "url": url,
    }


def _connect_external_context(playwright: Any, settings: dict[str, Any]) -> tuple[Any, Any]:
    cfg = _portal_cfg(settings)
    cdp_url = _cdp_url(cfg)
    if not _cdp_ready(cdp_url):
        raise PortalAssistantError(
            "Browser login KarirLog belum aktif. Jalankan portal_login.bat, login, lalu biarkan browser tetap terbuka."
        )
    try:
        browser = playwright.chromium.connect_over_cdp(
            cdp_url,
            timeout=int(cfg.get("timeout_ms", 45000)),
        )
    except Exception as exc:
        raise PortalAssistantError(f"Tidak dapat terhubung ke browser login: {exc}") from exc
    if not browser.contexts:
        raise PortalAssistantError("Browser terhubung tetapi context Chrome tidak tersedia")
    return browser, browser.contexts[0]


def _write_report(
    plan: PortalPrefillPlan,
    settings: dict[str, Any],
    *,
    status: str,
    filled: list[str],
    warnings: list[str],
    screenshot_path: str,
) -> dict[str, Any]:
    cfg = _portal_cfg(settings)
    artifact_dir = Path(str(cfg.get("artifact_dir", "data/output/portal_sessions")))
    session_dir = artifact_dir / f"application_{plan.application_id}"
    session_dir.mkdir(parents=True, exist_ok=True)
    report_path = session_dir / "portal_prefill_report.json"
    report = {
        "status": status,
        "application_id": plan.application_id,
        "company": plan.company,
        "title": plan.title,
        "url": plan.url,
        "filled": list(dict.fromkeys(filled)),
        "attachment_paths": plan.attachment_paths,
        "warnings": list(dict.fromkeys(warnings)),
        "screenshot_path": screenshot_path,
        "browser_mode": "external_chrome_cdp",
        "safety": "KarirLog tidak menekan tombol Lamar, Next, Apply, atau Submit dan tidak melewati CAPTCHA/OTP.",
        "manual_flow": True,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report["report_path"] = str(report_path)
    return report


def _close_session_pages(context: Any, pages_before: set[Any]) -> None:
    """Close only tabs created for the current queue item.

    Cookies/login stay in the shared browser context, while redirects from a
    submitted application cannot collide with navigation for the next item.
    """
    for page in list(getattr(context, "pages", [])):
        if page in pages_before:
            continue
        try:
            if not page.is_closed():
                page.close()
        except Exception:
            continue


def _open_isolated_plan_page(
    context: Any,
    plan: PortalPrefillPlan,
    cfg: dict[str, Any],
) -> Any:
    """Open each application in a fresh tab and retry interrupted navigation."""
    timeout_ms = int(cfg.get("timeout_ms", 45000))
    retry_count = max(1, int(cfg.get("navigation_retry_count", 3)))
    retry_delay = max(0.1, float(cfg.get("navigation_retry_delay_seconds", 0.75)))
    last_error: Exception | None = None

    for attempt in range(1, retry_count + 1):
        page = context.new_page()
        try:
            try:
                page.bring_to_front()
            except Exception:
                pass
            page.goto(
                plan.url,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            return page
        except Exception as exc:
            last_error = exc
            try:
                if not page.is_closed():
                    page.close()
            except Exception:
                pass
            if attempt < retry_count:
                time.sleep(retry_delay)

    raise PortalAssistantError(
        f"Halaman lowongan gagal dibuka setelah {retry_count} percobaan: {last_error}"
    ) from last_error


def _run_plan_in_context(
    context: Any,
    plan: PortalPrefillPlan,
    settings: dict[str, Any],
    *,
    interactive: bool,
) -> dict[str, Any]:
    if plan.warnings:
        raise PortalAssistantError("; ".join(plan.warnings))
    cfg = _portal_cfg(settings)
    artifact_dir = Path(str(cfg.get("artifact_dir", "data/output/portal_sessions")))
    session_dir = artifact_dir / f"application_{plan.application_id}"
    session_dir.mkdir(parents=True, exist_ok=True)

    # Never reuse the previous application's tab. KitaLulus may still be
    # redirecting it to /apply or /apply/success after the user confirms S.
    # Reusing that tab caused Playwright's next page.goto() to be interrupted.
    pages_before = set(getattr(context, "pages", []))
    page = _open_isolated_plan_page(context, plan, cfg)

    try:
        _inject_manual_helper(page, plan)

        filled: list[str] = []
        warnings: list[str] = []
        screenshot_path = ""
        status = "PORTAL_REVIEW_REQUIRED"
        if interactive:
            status, filled, warnings, screenshot_path = _interactive_manual_session(
                context, plan, cfg, session_dir
            )
        else:
            result = prefill_current_page(page, plan)
            filled.extend(result["filled"])
            warnings.extend(result["warnings"])
            screenshot_path = _safe_screenshot(
                page, session_dir / "page_before_submit.png"
            )
        return _write_report(
            plan,
            settings,
            status=status,
            filled=filled,
            warnings=warnings,
            screenshot_path=screenshot_path,
        )
    finally:
        if bool(cfg.get("close_completed_queue_tabs", True)):
            _close_session_pages(context, pages_before)


def run_external_portal_assistant(
    plan: PortalPrefillPlan,
    settings: dict[str, Any],
    interactive: bool = True,
) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise PortalAssistantError(
            "Playwright belum terpasang. Jalankan install_dependencies.bat."
        ) from exc

    cfg = _portal_cfg(settings)
    if bool(cfg.get("auto_launch_external_browser", True)) and not _cdp_ready(_cdp_url(cfg)):
        launch_portal_login_browser(settings, initial_url=plan.url)
        if interactive:
            print("\nBrowser normal sudah dibuka. Login ke portal terlebih dahulu.")
            try:
                input("Setelah login selesai, kembali ke terminal lalu tekan ENTER...")
            except (EOFError, KeyboardInterrupt):
                pass

    with sync_playwright() as playwright:
        _browser, context = _connect_external_context(playwright, settings)
        return _run_plan_in_context(
            context, plan, settings, interactive=interactive
        )


def run_external_portal_queue(
    plans: Iterable[PortalPrefillPlan],
    settings: dict[str, Any],
    interactive: bool = True,
) -> Iterator[dict[str, Any]]:
    plan_list = list(plans)
    if not plan_list:
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise PortalAssistantError(
            "Playwright belum terpasang. Jalankan install_dependencies.bat."
        ) from exc

    cfg = _portal_cfg(settings)
    if bool(cfg.get("auto_launch_external_browser", True)) and not _cdp_ready(_cdp_url(cfg)):
        launch_portal_login_browser(settings, initial_url=plan_list[0].url)
        if interactive:
            print("\nBrowser normal sudah dibuka menggunakan profil KarirLog.")
            print("Login ke portal sekali. Sesi akan dipakai untuk seluruh antrean.")
            try:
                input("Setelah login selesai, kembali ke terminal lalu tekan ENTER...")
            except (EOFError, KeyboardInterrupt):
                pass

    with sync_playwright() as playwright:
        _browser, context = _connect_external_context(playwright, settings)
        total = len(plan_list)
        for index, plan in enumerate(plan_list, start=1):
            print("\n" + "#" * 64)
            print(f"ANTREAN PORTAL {index}/{total} | Application #{plan.application_id}")
            print("#" * 64)
            try:
                report = _run_plan_in_context(
                    context, plan, settings, interactive=interactive
                )
            except PortalAssistantError as exc:
                report = _write_report(
                    plan,
                    settings,
                    status="PORTAL_ASSIST_FAILED",
                    filled=[],
                    warnings=[str(exc)],
                    screenshot_path="",
                )
            yield report

            if interactive and index < total:
                try:
                    command = input(
                        "\n[ENTER] Buka lowongan berikutnya | [X] Hentikan antrean: "
                    ).strip().lower()
                except (EOFError, KeyboardInterrupt):
                    command = "x"
                if command in {"x", "stop", "berhenti"}:
                    break
