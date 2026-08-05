from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


class PortalAssistantError(RuntimeError):
    pass


@dataclass(slots=True)
class PortalPrefillPlan:
    application_id: int
    url: str
    full_name: str
    email: str
    phone: str
    cv_path: str
    cover_letter_path: str
    company: str = ""
    title: str = ""
    attachment_paths: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _manifest_attachments(output_path: Path) -> list[Path]:
    manifest_path = output_path / "package_manifest.json"
    if not manifest_path.exists():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    entries = manifest.get("attachments", [])
    if not isinstance(entries, list):
        return []
    ordered = sorted(
        (entry for entry in entries if isinstance(entry, dict)),
        key=lambda entry: int(entry.get("order", 999999)),
    )
    result: list[Path] = []
    root = output_path.resolve()
    for entry in ordered:
        relative = str(entry.get("path", "")).strip()
        if not relative:
            continue
        path = (output_path / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if path.exists() and path.is_file():
            result.append(path)
    return result


def build_prefill_plan(
    application: dict[str, Any], profile: dict[str, Any]
) -> PortalPrefillPlan:
    if str(application.get("apply_channel", "")) != "PORTAL":
        raise PortalAssistantError("Application bukan channel PORTAL")
    url = str(application.get("recipient", "")).strip()
    if not url.startswith(("http://", "https://")):
        raise PortalAssistantError("URL portal tidak valid")
    output_path = Path(str(application.get("output_path", "")))

    package_attachments = _manifest_attachments(output_path)
    if not package_attachments:
        attachment_folder = output_path / "attachments"
        package_attachments = (
            sorted(
                (path for path in attachment_folder.iterdir() if path.is_file()),
                key=lambda path: path.name.lower(),
            )
            if attachment_folder.exists()
            else []
        )
    cv_path = (
        package_attachments[0]
        if package_attachments
        else Path(str(application.get("selected_cv_path", "")))
    )
    warnings: list[str] = []
    if not cv_path.exists():
        warnings.append("CV untuk upload tidak ditemukan")
    cover_letter = output_path / "cover_letter.txt"
    if not cover_letter.exists():
        warnings.append("Cover letter tidak ditemukan")

    fields = ["full_name", "email", "phone", "cv"]
    if cover_letter.exists():
        fields.append("cover_letter")
    if len(package_attachments) > 1:
        fields.append("additional_attachments")
    return PortalPrefillPlan(
        application_id=int(application["id"]),
        url=url,
        full_name=str(profile.get("full_name", "")).strip(),
        email=str(profile.get("email", "")).strip(),
        phone=str(profile.get("phone", "")).strip(),
        cv_path=str(cv_path),
        cover_letter_path=str(cover_letter),
        company=str(application.get("company", "")).strip(),
        title=str(application.get("title", "")).strip(),
        attachment_paths=[str(path) for path in package_attachments],
        fields=fields,
        warnings=warnings,
    )


def _fill_first(locator: Any, value: str) -> bool:
    try:
        count = locator.count()
    except Exception:
        return False
    for index in range(count):
        try:
            item = locator.nth(index)
            if not item.is_visible() or not item.is_enabled():
                continue
            item.fill(value)
            return True
        except Exception:
            continue
    return False


def _try_fill(
    page: Any,
    labels: list[str],
    value: str,
    selectors: list[str] | None = None,
) -> bool:
    if not value:
        return False
    for label in labels:
        try:
            if _fill_first(page.get_by_label(label, exact=False), value):
                return True
        except Exception:
            continue
    for label in labels:
        try:
            if _fill_first(page.get_by_placeholder(label, exact=False), value):
                return True
        except Exception:
            continue
    for selector in selectors or []:
        try:
            if _fill_first(page.locator(selector), value):
                return True
        except Exception:
            continue
    return False


def _try_upload_documents(page: Any, plan: PortalPrefillPlan) -> tuple[list[str], list[str]]:
    filled: list[str] = []
    warnings: list[str] = []
    try:
        file_inputs = page.locator('input[type="file"]')
        count = file_inputs.count()
    except Exception as exc:
        return filled, [f"Pemeriksaan upload gagal: {exc}"]
    if count == 0:
        return filled, ["Input upload CV belum ditemukan pada halaman aktif"]

    upload_paths = plan.attachment_paths or [plan.cv_path]
    valid_paths = [path for path in upload_paths if Path(path).is_file()]
    if not valid_paths:
        return filled, ["File CV/lampiran tidak tersedia untuk upload"]

    for index in range(count):
        try:
            item = file_inputs.nth(index)
            accepts_multiple = item.get_attribute("multiple") is not None
            if accepts_multiple and len(valid_paths) > 1:
                item.set_input_files(valid_paths)
                filled.extend(["cv", "additional_attachments"])
            else:
                item.set_input_files(valid_paths[0])
                filled.append("cv")
                if len(valid_paths) > 1:
                    warnings.append(
                        f"Portal hanya menerima satu file pada input yang ditemukan. {len(valid_paths) - 1} lampiran tambahan perlu diunggah manual."
                    )
            return list(dict.fromkeys(filled)), warnings
        except Exception:
            continue
    warnings.append("Input file ditemukan tetapi upload otomatis gagal; pilih CV secara manual")
    return filled, warnings


def _read_cover_letter(plan: PortalPrefillPlan) -> str:
    try:
        return Path(plan.cover_letter_path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def prefill_current_page(page: Any, plan: PortalPrefillPlan) -> dict[str, Any]:
    """Prefill only the active page. Never clicks Apply, Next, or Submit."""
    filled: list[str] = []
    warnings: list[str] = []

    if _try_fill(
        page,
        ["Full name", "Name", "Nama lengkap", "Nama"],
        plan.full_name,
        [
            'input[autocomplete="name"]',
            'input[name*="full_name" i]',
            'input[name*="fullname" i]',
            'input[name="name" i]',
        ],
    ):
        filled.append("full_name")
    if _try_fill(
        page,
        ["Email", "Email address", "Alamat email"],
        plan.email,
        [
            'input[type="email"]',
            'input[autocomplete="email"]',
            'input[name*="email" i]',
        ],
    ):
        filled.append("email")
    if _try_fill(
        page,
        ["Phone", "Phone number", "Nomor telepon", "Nomor HP", "No. HP", "No HP"],
        plan.phone,
        [
            'input[type="tel"]',
            'input[autocomplete="tel"]',
            'input[name*="phone" i]',
            'input[name*="mobile" i]',
            'input[name*="whatsapp" i]',
        ],
    ):
        filled.append("phone")

    upload_filled, upload_warnings = _try_upload_documents(page, plan)
    filled.extend(upload_filled)
    warnings.extend(upload_warnings)

    cover = _read_cover_letter(plan)
    if cover and _try_fill(
        page,
        [
            "Cover letter",
            "Motivation",
            "Message",
            "Pesan",
            "Surat lamaran",
            "Alasan melamar",
        ],
        cover,
        [
            'textarea[name*="cover" i]',
            'textarea[name*="message" i]',
            'textarea[name*="motivation" i]',
            'textarea[name*="reason" i]',
        ],
    ):
        filled.append("cover_letter")

    if not filled:
        warnings.append(
            "Belum ada field umum yang terdeteksi. Login, klik Lamar, atau lanjutkan ke halaman form lalu scan ulang."
        )
    return {
        "filled": list(dict.fromkeys(filled)),
        "warnings": list(dict.fromkeys(warnings)),
        "url": str(getattr(page, "url", "")),
    }


def _inject_manual_helper(page: Any, plan: PortalPrefillPlan) -> bool:
    cover = _read_cover_letter(plan)
    payload = {
        "name": plan.full_name,
        "email": plan.email,
        "phone": plan.phone,
        "cv": str(Path(plan.cv_path).resolve()),
        "cover": cover,
        "company": plan.company,
        "title": plan.title,
    }
    script = r"""
(data) => {
  const old = document.getElementById('karirlog-manual-helper');
  if (old) old.remove();
  const root = document.createElement('div');
  root.id = 'karirlog-manual-helper';
  root.style.cssText = [
    'position:fixed','right:16px','bottom:16px','z-index:2147483647',
    'width:330px','max-height:70vh','overflow:auto','background:#111827',
    'color:#f9fafb','border:1px solid #374151','border-radius:12px',
    'box-shadow:0 12px 30px rgba(0,0,0,.35)','padding:14px',
    'font:13px/1.45 Arial,sans-serif'
  ].join(';');
  const esc = (v) => String(v || '').replace(/[&<>"']/g, (c) => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
  const rows = [
    ['Nama', data.name], ['Email', data.email], ['Telepon', data.phone]
  ];
  root.innerHTML = `
    <div style="font-weight:700;font-size:15px;margin-bottom:4px">KarirLog Manual Assist</div>
    <div style="color:#9ca3af;margin-bottom:10px">${esc(data.company)} — ${esc(data.title)}</div>
    <div id="kl-rows"></div>
    <div style="margin-top:8px;color:#9ca3af">CV</div>
    <div style="word-break:break-all;background:#1f2937;padding:7px;border-radius:7px">${esc(data.cv)}</div>
    <button id="kl-copy-cover" style="margin-top:9px;width:100%;padding:7px;border:0;border-radius:7px;cursor:pointer">Salin cover letter</button>
    <div id="kl-msg" style="margin-top:7px;color:#93c5fd"></div>
    <div style="margin-top:9px;color:#fbbf24">Isi pertanyaan tambahan dan tekan Submit sendiri. KarirLog tidak pernah menekan Submit.</div>`;
  document.documentElement.appendChild(root);
  const rowsEl = root.querySelector('#kl-rows');
  const copy = async (value, label) => {
    try {
      await navigator.clipboard.writeText(String(value || ''));
      root.querySelector('#kl-msg').textContent = `${label} disalin.`;
    } catch (_) {
      const ta = document.createElement('textarea');
      ta.value = String(value || ''); document.body.appendChild(ta); ta.select();
      document.execCommand('copy'); ta.remove();
      root.querySelector('#kl-msg').textContent = `${label} disalin.`;
    }
  };
  rows.forEach(([label, value]) => {
    const row = document.createElement('div');
    row.style.cssText = 'display:grid;grid-template-columns:70px 1fr auto;gap:6px;align-items:center;margin:5px 0';
    row.innerHTML = `<span style="color:#9ca3af">${esc(label)}</span><span style="word-break:break-all">${esc(value)}</span>`;
    const btn = document.createElement('button');
    btn.textContent = 'Salin'; btn.style.cssText = 'padding:4px 7px;border:0;border-radius:6px;cursor:pointer';
    btn.addEventListener('click', () => copy(value, label)); row.appendChild(btn); rowsEl.appendChild(row);
  });
  root.querySelector('#kl-copy-cover').addEventListener('click', () => copy(data.cover, 'Cover letter'));
  return true;
}
"""
    try:
        return bool(page.evaluate(script, payload))
    except Exception:
        return False


def _current_page(context: Any) -> Any | None:
    for page in reversed(list(context.pages)):
        try:
            if not page.is_closed():
                return page
        except Exception:
            continue
    return None


def _launch_context(playwright: Any, user_data_dir: Path, cfg: dict[str, Any]) -> Any:
    kwargs: dict[str, Any] = {
        "headless": bool(cfg.get("headless", False)),
        "accept_downloads": True,
        "no_viewport": True,
    }
    slow_mo = int(cfg.get("slow_mo_ms", 0) or 0)
    if slow_mo > 0:
        kwargs["slow_mo"] = slow_mo

    browser_channel = str(cfg.get("browser_channel", "auto")).strip().lower()
    if browser_channel in {"chrome", "msedge"}:
        kwargs["channel"] = browser_channel
        return playwright.chromium.launch_persistent_context(str(user_data_dir), **kwargs)
    if browser_channel == "auto":
        try:
            return playwright.chromium.launch_persistent_context(
                str(user_data_dir), channel="chrome", **kwargs
            )
        except Exception:
            pass
    return playwright.chromium.launch_persistent_context(str(user_data_dir), **kwargs)


def _safe_screenshot(page: Any, path: Path) -> str:
    try:
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return ""


def _interactive_manual_session(
    context: Any,
    plan: PortalPrefillPlan,
    cfg: dict[str, Any],
    session_dir: Path,
) -> tuple[str, list[str], list[str], str]:
    filled: list[str] = []
    warnings: list[str] = []
    scan_no = 0
    last_screenshot = ""

    print("\n" + "=" * 64)
    print(f"PORTAL MANUAL ASSIST — Application #{plan.application_id}")
    print(f"{plan.company} — {plan.title}")
    print("=" * 64)
    print("1. Login ke portal bila diminta.")
    print("2. Klik tombol Lamar/Apply sendiri dan masuk sampai form lamaran.")
    print("3. Kembali ke terminal, lalu tekan ENTER untuk scan + prefill halaman aktif.")
    print("4. Isi pertanyaan lain dan tekan Submit sendiri di browser.")
    print("Sesi login disimpan di data/browser_profile untuk pemakaian berikutnya.")

    while True:
        try:
            choice = input(
                "\n[ENTER] Scan/prefill ulang | [R] Selesai review (belum submit) | "
                "[S] Sudah submit | [Q] Batal: "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            choice = "q"

        if choice in {"q", "quit", "batal"}:
            return "DRAFT_READY_PORTAL", filled, warnings, last_screenshot
        if choice in {"r", "review"}:
            return "PORTAL_REVIEW_REQUIRED", filled, warnings, last_screenshot
        if choice in {"s", "submitted", "submit"}:
            return "PORTAL_SUBMITTED", filled, warnings, last_screenshot

        page = _current_page(context)
        if page is None:
            warnings.append("Browser sudah ditutup. Sesi dibatalkan.")
            return "DRAFT_READY_PORTAL", filled, warnings, last_screenshot
        try:
            page.wait_for_load_state(
                "domcontentloaded", timeout=int(cfg.get("timeout_ms", 45000))
            )
        except Exception:
            pass
        scan_no += 1
        result = prefill_current_page(page, plan)
        filled.extend(result["filled"])
        warnings.extend(result["warnings"])
        helper_ok = _inject_manual_helper(page, plan) if cfg.get("show_helper_panel", True) else False
        shot = session_dir / f"scan_{scan_no:02d}.png"
        last_screenshot = _safe_screenshot(page, shot) or last_screenshot

        print(f"Halaman aktif : {result.get('url') or '-'}")
        print(f"Terisi        : {', '.join(result['filled']) if result['filled'] else '-'}")
        if result["warnings"]:
            for warning in result["warnings"]:
                print(f"Catatan       : {warning}")
        if cfg.get("show_helper_panel", True):
            print(f"Helper panel  : {'aktif' if helper_ok else 'tidak dapat ditampilkan'}")
        print("Lanjutkan di browser. Scan ulang setiap kali form berpindah halaman.")


def run_portal_assistant(
    plan: PortalPrefillPlan,
    settings: dict[str, Any],
    interactive: bool = True,
) -> dict[str, Any]:
    if plan.warnings:
        raise PortalAssistantError("; ".join(plan.warnings))

    cfg = settings.get("portal_assistant", {})
    browser_mode = str(cfg.get("browser_mode", "external_chrome")).strip().lower()
    if browser_mode in {"external_chrome", "external_cdp", "cdp"}:
        from .portal_queue import run_external_portal_assistant

        return run_external_portal_assistant(
            plan, settings, interactive=interactive
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - optional runtime dependency
        raise PortalAssistantError(
            "Playwright belum terpasang. Jalankan install_dependencies.bat dan install_browser.bat."
        ) from exc

    user_data_dir = Path(str(cfg.get("user_data_dir", "data/browser_profile")))
    artifact_dir = Path(str(cfg.get("artifact_dir", "data/output/portal_sessions")))
    session_dir = artifact_dir / f"application_{plan.application_id}"
    session_dir.mkdir(parents=True, exist_ok=True)
    user_data_dir.mkdir(parents=True, exist_ok=True)
    report_path = session_dir / "portal_prefill_report.json"
    filled: list[str] = []
    warnings: list[str] = []
    screenshot_path = ""
    final_status = "PORTAL_REVIEW_REQUIRED"

    with sync_playwright() as playwright:
        try:
            context = _launch_context(playwright, user_data_dir, cfg)
        except Exception as exc:
            raise PortalAssistantError(
                f"Browser tidak dapat dibuka: {exc}. Jalankan install_browser.bat."
            ) from exc
        try:
            page = _current_page(context) or context.new_page()
            page.goto(
                plan.url,
                wait_until="domcontentloaded",
                timeout=int(cfg.get("timeout_ms", 45000)),
            )
            _inject_manual_helper(page, plan)

            if interactive:
                final_status, filled, warnings, screenshot_path = _interactive_manual_session(
                    context, plan, cfg, session_dir
                )
            else:
                result = prefill_current_page(page, plan)
                filled.extend(result["filled"])
                warnings.extend(result["warnings"])
                screenshot_path = _safe_screenshot(
                    page, session_dir / "page_before_submit.png"
                )
        finally:
            context.close()

    report = {
        "status": final_status,
        "application_id": plan.application_id,
        "company": plan.company,
        "title": plan.title,
        "url": plan.url,
        "filled": list(dict.fromkeys(filled)),
        "attachment_paths": plan.attachment_paths,
        "warnings": list(dict.fromkeys(warnings)),
        "screenshot_path": screenshot_path,
        "safety": "KarirLog tidak menekan tombol Lamar, Next, Apply, atau Submit dan tidak melewati CAPTCHA/OTP.",
        "manual_flow": True,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report["report_path"] = str(report_path)
    return report
