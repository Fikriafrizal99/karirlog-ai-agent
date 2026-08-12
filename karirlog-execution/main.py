"""KarirLog Execution Engine entrypoint.

Reads the discovery CSV produced by the Search Engine, then runs analysis →
decision → package build → delivery prep → persistence → Telegram summary.

Usage:
    python main.py execute --input data/input/discovery_latest.csv
    python main.py scheduled-run
    python main.py create-gmail-drafts | approve-email | send-email | ...
    python main.py list-applications | list | list-audit | check-* | reset

Never imports the discovery package — the CSV is the only handoff.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

# Make src/ and the sibling contracts package importable without packaging.
_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT.parent / "karirlog-contracts" / "src"))

# Windows consoles default to cp1252; summaries contain emoji/box chars.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv optional
    load_dotenv = None

from karirlog_execution.config import load_json, load_settings
from karirlog_execution.cv_selector import audit_cv_library
from karirlog_execution.database import Database
from karirlog_execution.delivery_workflow import (
    assist_portal_application,
    assist_portal_queue,
    create_pending_gmail_drafts,
    prepare_email_approval,
    send_email_with_approval,
)
from karirlog_execution.document_library import audit_document_library
from karirlog_execution.gmail_delivery import GmailDeliveryError, gmail_readiness
from karirlog_execution.input_loader import InputLoaderError, load_jobs_from_csv
from karirlog_execution.logging_setup import setup_logging
from karirlog_execution.notifications import (
    build_application_report,
    build_delivery_summary,
    build_portal_queue_summary,
    build_summary,
    send_telegram,
)
from karirlog_execution.pipeline import run_pipeline
from karirlog_execution.portal_assistant import PortalAssistantError
from karirlog_execution.portal_queue import launch_portal_login_browser
from karirlog_execution.paths import resolve_settings


def _load_settings(settings_path: str) -> dict[str, Any]:
    return resolve_settings(load_settings(settings_path), _ROOT)


def _load_profile_settings(
    profile_path: str, settings_path: str, analysis_mode: str | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = load_json(profile_path)
    settings = _load_settings(settings_path)
    if analysis_mode:
        settings["analysis_mode"] = analysis_mode
    return profile, settings


def command_execute(
    profile_path: str,
    settings_path: str,
    input_path: str | None,
    analysis_mode: str | None,
    force_reprocess: bool = False,
    rebuild_packages: bool = False,
) -> int:
    try:
        profile, settings = _load_profile_settings(
            profile_path, settings_path, analysis_mode
        )
    except (OSError, ValueError, TypeError) as exc:
        print(
            "ERROR: konfigurasi execution belum siap. "
            f"Periksa profile/settings: {exc}"
        )
        return 2
    settings["force_reprocess"] = bool(force_reprocess)
    settings["rebuild_packages"] = bool(rebuild_packages)
    logger = setup_logging(settings.get("output_dir", "data/output"))
    csv_path = input_path or settings.get("input_csv", "data/input/discovery_latest.csv")
    try:
        load_result = load_jobs_from_csv(csv_path)
    except InputLoaderError as exc:
        logger.error("Gagal memuat CSV input: %s", exc)
        print(f"ERROR: {exc}")
        return 2

    print(f"Input CSV        : {csv_path}")
    print(f"Total baris      : {load_result.total_rows}")
    print(f"Baris valid      : {load_result.valid}")
    print(f"Baris ditolak    : {load_result.failed}")
    print(f"Duplikat CSV     : {load_result.duplicates}")
    for message in load_result.errors[:20]:
        print(f"  - {message}")
    if not load_result.jobs:
        # Even an empty handoff initializes the configured database so the
        # first execution is deterministic and creates its runtime folders.
        database = Database(settings["database_path"])
        database.close()
        print("Tidak ada lowongan valid untuk diproses. Selesai tanpa error.")
        return 0

    stats = run_pipeline(load_result.jobs, profile, settings)
    print("\n" + build_summary(stats) + "\n")
    print(f"Report: {stats['report_path']}")
    for item in stats["results"]:
        print(
            f"- {item['decision']:6} | {item['score']:3} | "
            f"{item.get('analysis_mode', 'ERROR'):13} | "
            f"{item.get('lifecycle_state', '-'):14} | "
            f"{item.get('application_status', 'NOT_BUILT'):22} | "
            f"{item['company']} — {item['title']}"
        )
    return 0 if not stats.get("analysis_failures") else 2


def command_scheduled_run(profile_path: str, settings_path: str, input_path: str | None) -> int:
    profile, settings = _load_profile_settings(profile_path, settings_path)
    setup_logging(settings.get("output_dir", "data/output"))
    csv_path = input_path or settings.get("input_csv", "data/input/discovery_latest.csv")
    try:
        load_result = load_jobs_from_csv(csv_path)
    except InputLoaderError as exc:
        print(f"ERROR: {exc}")
        return 2
    if load_result.jobs:
        stats = run_pipeline(load_result.jobs, profile, settings)
        print(build_summary(stats))
    else:
        print("CSV kosong; melewati analisis.")
    if settings.get("scheduler", {}).get("create_gmail_drafts", True):
        delivery = create_pending_gmail_drafts(profile, settings)
        print("\n" + build_delivery_summary(delivery))
        if settings.get("telegram_enabled", False):
            send_telegram(settings, build_delivery_summary(delivery))
        return 2 if delivery.get("failed") else 0
    return 0

def command_check_ai(settings_path: str) -> int:
    settings = _load_settings(settings_path)
    mode = str(settings.get("analysis_mode", "ai_with_fallback"))
    env_name = str(settings.get("openai_api_key_env", "OPENAI_API_KEY"))
    ready = bool(os.getenv(env_name, "").strip())
    print(
        f"Analysis mode : {mode}\nAI model      : {settings.get('ai_model', '')}\n"
        f"API key       : {'READY' if ready else 'MISSING'}"
    )
    if mode == "ai_required" and not ready:
        return 2
    return 0


def command_check_cv(profile_path: str, settings_path: str) -> int:
    profile, settings = _load_profile_settings(profile_path, settings_path)
    rows = audit_cv_library(profile, settings)
    invalid = 0
    for row in rows:
        if not row["enabled"]:
            status, detail = "DISABLED", "Profil tidak aktif"
        elif row["valid"]:
            status, detail = "READY", f"{row['size']} byte | {row['sha256'][:12]}..."
        else:
            status, detail = "MISSING", "; ".join(row["warnings"])
            invalid += 1
        print(f"- {status:8} | {row['cv_id']:20} | {row['path']} | {detail}")
    return 2 if invalid else 0


def command_check_documents(profile_path: str, settings_path: str) -> int:
    profile, settings = _load_profile_settings(profile_path, settings_path)
    rows = audit_document_library(profile, settings)
    for row in rows:
        state = "READY" if row["enabled"] else "DISABLED"
        cv_location = row["cv_folder"] or row["legacy_cv_path"] or "-"
        print(
            f"- {state:8} | {row['profile_id']:20} | "
            f"CV={cv_location} | Attachment={row['attachment_count']} | "
            f"Supporting={row['supporting_document_count']}"
        )
    return 0


def command_check_gmail(profile_path: str, settings_path: str) -> int:
    profile, settings = _load_profile_settings(profile_path, settings_path)
    checks = gmail_readiness(settings, profile)
    for key, status in checks:
        print(f"- {key:15}: {status}")
    critical = dict(checks)
    if critical["enabled"] == "READY" and (
        critical["credentials"] != "READY" or critical["profile_email"] != "READY"
    ):
        return 2
    return 0


def command_create_gmail_drafts(profile_path: str, settings_path: str, limit: int) -> int:
    profile, settings = _load_profile_settings(profile_path, settings_path)
    result = create_pending_gmail_drafts(profile, settings, limit=limit)
    summary = build_delivery_summary(result)
    print(summary)
    if settings.get("telegram_enabled", False):
        send_telegram(settings, summary)
    for item in result.get("items", []):
        print(f"- Application #{item['application_id']}: {item['status']} {item.get('error', '')}")
    return 2 if result.get("failed") else 0


def command_approve_email(settings_path: str, application_id: int) -> int:
    settings = _load_settings(settings_path)
    try:
        code = prepare_email_approval(settings, application_id)
    except GmailDeliveryError as exc:
        print(f"Approval gagal: {exc}")
        return 2
    print("Kode approval dibuat. Periksa draft Gmail sebelum melanjutkan.")
    print(f"Kode: {code}")
    print(f"Kirim dengan: send-email --application-id {application_id} --confirm {code}")
    return 0


def command_send_email(settings_path: str, application_id: int, confirmation: str) -> int:
    settings = _load_settings(settings_path)
    try:
        result = send_email_with_approval(settings, application_id, confirmation)
    except GmailDeliveryError as exc:
        print(f"Pengiriman ditolak/gagal: {exc}")
        return 2
    message = f"✅ KarirLog: email Application #{application_id} berhasil dikirim."
    print(f"Email terkirim. Application #{application_id} | Message ID {result['message_id']}")
    if settings.get("telegram_enabled", False):
        send_telegram(settings, message)
    return 0


def command_portal_login(settings_path: str, url: str = "") -> int:
    settings = _load_settings(settings_path)
    try:
        result = launch_portal_login_browser(settings, initial_url=url.strip() or None)
    except PortalAssistantError as exc:
        print(f"Portal login gagal: {exc}")
        return 2
    print("Browser login KarirLog siap.")
    print(f"Mode       : {result.get('status', '-')}")
    print(f"CDP        : {result.get('cdp_url', '-')}")
    print(f"Profile    : {result.get('user_data_dir', '-')}")
    print("Login ke portal di browser tersebut dan biarkan browser tetap terbuka.")
    return 0


def command_assist_portal_queue(profile_path: str, settings_path: str, limit: int) -> int:
    profile, settings = _load_profile_settings(profile_path, settings_path)
    try:
        result = assist_portal_queue(profile, settings, limit=limit, interactive=True)
    except PortalAssistantError as exc:
        print(f"Antrean portal gagal: {exc}")
        return 2
    print("\nKARIRLOG PORTAL QUEUE SELESAI")
    print(f"Antrean    : {result.get('queued', 0)}")
    print(f"Diproses   : {result.get('processed', 0)}")
    print(f"Submitted  : {result.get('submitted', 0)}")
    print(f"Review     : {result.get('review', 0)}")
    print(f"Dilewati   : {result.get('skipped', 0)}")
    print(f"Gagal      : {result.get('failed', 0)}")

    report_cfg = settings.get("telegram_application_report", {})
    if settings.get("telegram_enabled", False) and report_cfg.get("auto_after_portal_queue", True):
        database = Database(settings["database_path"])
        try:
            rows = database.list_applications(max(1, int(report_cfg.get("limit", 50))))
            message = (
                build_portal_queue_summary(result)
                + "\n\n"
                + build_application_report(rows)
            )
        finally:
            database.close()
        sent, detail = send_telegram(settings, message)
        print(f"Telegram   : {detail}")
        if not sent:
            return 2
    return 2 if result.get("failed") else 0


def command_assist_portal(profile_path: str, settings_path: str, application_id: int) -> int:
    profile, settings = _load_profile_settings(profile_path, settings_path)
    try:
        result = assist_portal_application(profile, settings, application_id)
    except PortalAssistantError as exc:
        print(f"Portal assistant gagal: {exc}")
        return 2
    print(f"Status: {result.get('status')} | Report: {result.get('report_path', '-')}")
    return 0


def command_mark_portal_submitted(settings_path: str, application_id: int) -> int:
    settings = _load_settings(settings_path)
    database = Database(settings["database_path"])
    try:
        app = database.get_application(application_id)
        if not app:
            print("Application tidak ditemukan")
            return 2
        current_status = str(app.get("status") or "")
        allowed_statuses = {"PORTAL_REVIEW_REQUIRED", "PORTAL_ASSIST_FAILED"}
        if current_status == "PORTAL_SUBMITTED":
            print("Application sudah berstatus PORTAL_SUBMITTED")
            return 0
        if current_status not in allowed_statuses:
            print(
                "Hanya status PORTAL_REVIEW_REQUIRED atau PORTAL_ASSIST_FAILED "
                "yang dapat ditandai submitted"
            )
            return 2
        database.update_delivery(application_id, status="PORTAL_SUBMITTED", sent=True)
        database.set_lifecycle_state(int(app["job_id"]), "APPLIED")
        database.record_event(
            "PORTAL_SUBMITTED",
            application_id=application_id,
            job_id=int(app["job_id"]),
            status="PORTAL_SUBMITTED",
            detail=(
                "Pengguna mengonfirmasi submit portal secara manual "
                f"dari status {current_status}."
            ),
        )
        message = f"✅ KarirLog: Application #{application_id} ditandai PORTAL_SUBMITTED."
        print(message)
        if settings.get("telegram_enabled", False):
            send_telegram(settings, message)
        return 0
    finally:
        database.close()


def command_list(settings_path: str, limit: int) -> int:
    settings = _load_settings(settings_path)
    database = Database(settings["database_path"])
    try:
        rows = database.list_jobs(limit)
        for row in rows:
            print(
                f"#{row['id']:03} | {str(row['decision'] or '-'):6} | "
                f"{int(row['score'] or 0):3} | {str(row['analysis_mode'] or '-'):13} | "
                f"{row['company']} — {row['title']}"
            )
        if not rows:
            print("Belum ada lowongan.")
        return 0
    finally:
        database.close()


def command_list_applications(settings_path: str, limit: int) -> int:
    settings = _load_settings(settings_path)
    database = Database(settings["database_path"])
    try:
        rows = database.list_applications(limit)
        for row in rows:
            external = row["gmail_message_id"] or row["gmail_draft_id"] or "-"
            lifecycle_state = row["lifecycle_state"] if "lifecycle_state" in row.keys() else "-"
            print(
                f"#{row['id']:03} | {row['status']:24} | {lifecycle_state:14} | "
                f"{row['apply_channel'] or '-':6} | CV={row['selected_cv_id'] or '-'} | "
                f"External={external} | {row['company']} — {row['title']}"
            )
            if row["last_error"]:
                print(f"  Error: {row['last_error']}")
        if not rows:
            print("Belum ada lamaran.")
        return 0
    finally:
        database.close()


def command_telegram_application_report(settings_path: str, limit: int) -> int:
    settings = _load_settings(settings_path)
    database = Database(settings["database_path"])
    try:
        rows = database.list_applications(max(1, int(limit)))
        message = build_application_report(rows)
    finally:
        database.close()
    print(message)
    sent, detail = send_telegram(settings, message)
    print(f"\nTelegram: {detail}")
    return 0 if sent else 2


def command_list_audit(settings_path: str, limit: int) -> int:
    settings = _load_settings(settings_path)
    database = Database(settings["database_path"])
    try:
        rows = database.list_audit(limit)
        for row in rows:
            print(
                f"#{row['id']:03} | {row['created_at']} | {row['event_type']:25} | "
                f"App={row['application_id'] or '-'} | {row['company'] or '-'} — {row['title'] or '-'}"
            )
            if row["detail"]:
                print(f"  {row['detail']}")
        if not rows:
            print("Audit trail masih kosong.")
        return 0
    finally:
        database.close()


def command_reset(settings_path: str) -> int:
    import shutil

    settings = _load_settings(settings_path)
    database_path = Path(settings["database_path"])
    for candidate in (
        database_path,
        Path(str(database_path) + "-shm"),
        Path(str(database_path) + "-wal"),
    ):
        if candidate.exists():
            candidate.unlink()
    output_dir = Path(settings["output_dir"])
    if output_dir.exists():
        for child in output_dir.iterdir():
            if child.name == ".gitkeep":
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    print("Database dan output berhasil di-reset.")
    return 0

def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KarirLog Execution Engine")
    sub = parser.add_subparsers(dest="command", required=True)

    execute = sub.add_parser("execute", help="Baca CSV discovery, analisis, dan bangun paket lamaran")
    execute.add_argument("--input", default=None, help="Path CSV discovery (default dari settings)")
    execute.add_argument("--profile", default=str(_ROOT / "config" / "candidate_profile.json"))
    execute.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))
    execute.add_argument("--analysis-mode", choices=["rule_only", "ai_with_fallback", "ai_required"])
    execute.add_argument(
        "--force-reprocess",
        action="store_true",
        help="Analisis ulang job pada eksekusi ini saja",
    )
    execute.add_argument(
        "--rebuild-packages",
        action="store_true",
        help="Bangun ulang package pada eksekusi ini saja",
    )

    scheduled = sub.add_parser("scheduled-run", help="Execute dari CSV lalu buat draft Gmail")
    scheduled.add_argument("--input", default=None)
    scheduled.add_argument("--profile", default=str(_ROOT / "config" / "candidate_profile.json"))
    scheduled.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))

    for name, help_text in (
        ("check-ai", "Cek kesiapan AI"),
        ("check-gmail", "Cek kesiapan Gmail OAuth"),
    ):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))
        if name == "check-gmail":
            cmd.add_argument("--profile", default=str(_ROOT / "config" / "candidate_profile.json"))

    cv_cmd = sub.add_parser("check-cv", help="Validasi CV library")
    cv_cmd.add_argument("--profile", default=str(_ROOT / "config" / "candidate_profile.json"))
    cv_cmd.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))

    documents_cmd = sub.add_parser("check-documents", help="Cek folder CV/attachment/supporting")
    documents_cmd.add_argument("--profile", default=str(_ROOT / "config" / "candidate_profile.json"))
    documents_cmd.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))

    gmail_cmd = sub.add_parser("create-gmail-drafts", help="Buat draft Gmail dari queue")
    gmail_cmd.add_argument("--profile", default=str(_ROOT / "config" / "candidate_profile.json"))
    gmail_cmd.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))
    gmail_cmd.add_argument("--limit", type=int, default=100)

    approve_cmd = sub.add_parser("approve-email", help="Buat kode approval email")
    approve_cmd.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))
    approve_cmd.add_argument("--application-id", type=int, required=True)

    send_cmd = sub.add_parser("send-email", help="Kirim draft dengan kode approval")
    send_cmd.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))
    send_cmd.add_argument("--application-id", type=int, required=True)
    send_cmd.add_argument("--confirm", required=True)

    login_cmd = sub.add_parser("portal-login", help="Buka Chrome dengan profil login portal")
    login_cmd.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))
    login_cmd.add_argument("--url", default="")

    portal_cmd = sub.add_parser("assist-portal", help="Buka satu sesi portal dan prefill halaman aktif")
    portal_cmd.add_argument("--profile", default=str(_ROOT / "config" / "candidate_profile.json"))
    portal_cmd.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))
    portal_cmd.add_argument("--application-id", type=int, required=True)

    portal_queue_cmd = sub.add_parser("assist-portal-queue", help="Proses semua DRAFT_READY_PORTAL")
    portal_queue_cmd.add_argument("--profile", default=str(_ROOT / "config" / "candidate_profile.json"))
    portal_queue_cmd.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))
    portal_queue_cmd.add_argument("--limit", type=int, default=100)

    submitted_cmd = sub.add_parser("mark-portal-submitted", help="Tandai portal sudah disubmit manual")
    submitted_cmd.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))
    submitted_cmd.add_argument("--application-id", type=int, required=True)

    list_cmd = sub.add_parser("list", help="Lihat histori lowongan")
    list_cmd.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))
    list_cmd.add_argument("--limit", type=int, default=20)

    apps_cmd = sub.add_parser("list-applications", help="Lihat status lamaran")
    apps_cmd.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))
    apps_cmd.add_argument("--limit", type=int, default=20)

    telegram_report_cmd = sub.add_parser(
        "telegram-application-report", help="Kirim daftar dan status lamaran ke Telegram"
    )
    telegram_report_cmd.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))
    telegram_report_cmd.add_argument("--limit", type=int, default=50)

    audit_cmd = sub.add_parser("list-audit", help="Lihat audit trail")
    audit_cmd.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))
    audit_cmd.add_argument("--limit", type=int, default=50)

    reset_cmd = sub.add_parser("reset", help="Reset database dan output test")
    reset_cmd.add_argument("--settings", default=str(_ROOT / "config" / "execution_settings.json"))
    return parser


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(override=True)
    args = make_parser().parse_args()
    commands = {
        "execute": lambda: command_execute(
            args.profile,
            args.settings,
            args.input,
            args.analysis_mode,
            args.force_reprocess,
            args.rebuild_packages,
        ),
        "scheduled-run": lambda: command_scheduled_run(args.profile, args.settings, args.input),
        "check-ai": lambda: command_check_ai(args.settings),
        "check-cv": lambda: command_check_cv(args.profile, args.settings),
        "check-documents": lambda: command_check_documents(args.profile, args.settings),
        "check-gmail": lambda: command_check_gmail(args.profile, args.settings),
        "create-gmail-drafts": lambda: command_create_gmail_drafts(args.profile, args.settings, args.limit),
        "approve-email": lambda: command_approve_email(args.settings, args.application_id),
        "send-email": lambda: command_send_email(args.settings, args.application_id, args.confirm),
        "portal-login": lambda: command_portal_login(args.settings, args.url),
        "assist-portal": lambda: command_assist_portal(args.profile, args.settings, args.application_id),
        "assist-portal-queue": lambda: command_assist_portal_queue(args.profile, args.settings, args.limit),
        "mark-portal-submitted": lambda: command_mark_portal_submitted(args.settings, args.application_id),
        "list": lambda: command_list(args.settings, args.limit),
        "list-applications": lambda: command_list_applications(args.settings, args.limit),
        "telegram-application-report": lambda: command_telegram_application_report(args.settings, args.limit),
        "list-audit": lambda: command_list_audit(args.settings, args.limit),
        "reset": lambda: command_reset(args.settings),
    }
    return commands[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
