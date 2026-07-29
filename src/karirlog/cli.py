from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .config import load_json
from .cv_selector import audit_cv_library
from .database import Database
from .document_library import audit_document_library
from .delivery_workflow import (
    assist_portal_application,
    assist_portal_queue,
    create_pending_gmail_drafts,
    prepare_email_approval,
    send_email_with_approval,
)
from .discovery import DiscoveryManager, export_discovery
from .gmail_delivery import GmailDeliveryError, gmail_readiness
from .notifications import (
    build_application_report,
    build_delivery_summary,
    build_portal_queue_summary,
    build_summary,
    send_telegram,
)
from .pipeline import run_pipeline
from .portal_assistant import PortalAssistantError
from .portal_queue import launch_portal_login_browser
from .scheduler import scheduler_readiness


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KarirLog AI Agent V1.1")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_cmd = subparsers.add_parser("run", help="Collect, analisis, dan buat paket lamaran")
    run_cmd.add_argument("--profile", default="config/profil.json")
    run_cmd.add_argument("--settings", default="config/settings.json")
    run_cmd.add_argument("--mode", choices=["live", "live_with_fallback", "sample", "all"])
    run_cmd.add_argument(
        "--analysis-mode", choices=["rule_only", "ai_with_fallback", "ai_required"]
    )

    scheduled_cmd = subparsers.add_parser(
        "scheduled-run", help="Pipeline terjadwal dan pembuatan draft Gmail"
    )
    scheduled_cmd.add_argument("--profile", default="config/profil.json")
    scheduled_cmd.add_argument("--settings", default="config/settings.json")

    collect_cmd = subparsers.add_parser("collect", help="Collect saja tanpa analisis/database")
    collect_cmd.add_argument("--profile", default="config/profil.json")
    collect_cmd.add_argument("--settings", default="config/settings.json")
    collect_cmd.add_argument("--mode", choices=["live", "live_with_fallback", "sample", "all"])
    collect_cmd.add_argument("--output", default="data/output/latest_collection.json")

    for name, help_text in (
        ("check-sources", "Cek kesiapan collector"),
        ("check-ai", "Cek kesiapan AI"),
        ("check-gmail", "Cek kesiapan Gmail OAuth"),
        ("check-scheduler", "Cek kesiapan scheduler"),
    ):
        cmd = subparsers.add_parser(name, help=help_text)
        cmd.add_argument("--settings", default="config/settings.json")
        if name == "check-gmail":
            cmd.add_argument("--profile", default="config/profil.json")

    cv_cmd = subparsers.add_parser("check-cv", help="Validasi CV library")
    cv_cmd.add_argument("--profile", default="config/profil.json")
    cv_cmd.add_argument("--settings", default="config/settings.json")

    documents_cmd = subparsers.add_parser(
        "check-documents", help="Cek folder CV, attachment, dan supporting document"
    )
    documents_cmd.add_argument("--profile", default="config/profil.json")
    documents_cmd.add_argument("--settings", default="config/settings.json")

    gmail_cmd = subparsers.add_parser("create-gmail-drafts", help="Buat draft Gmail dari queue")
    gmail_cmd.add_argument("--profile", default="config/profil.json")
    gmail_cmd.add_argument("--settings", default="config/settings.json")
    gmail_cmd.add_argument("--limit", type=int, default=100)

    approve_cmd = subparsers.add_parser("approve-email", help="Buat kode approval email")
    approve_cmd.add_argument("--settings", default="config/settings.json")
    approve_cmd.add_argument("--application-id", type=int, required=True)

    send_cmd = subparsers.add_parser("send-email", help="Kirim draft dengan kode approval")
    send_cmd.add_argument("--settings", default="config/settings.json")
    send_cmd.add_argument("--application-id", type=int, required=True)
    send_cmd.add_argument("--confirm", required=True)

    login_cmd = subparsers.add_parser(
        "portal-login", help="Buka Chrome normal dengan profil login portal KarirLog"
    )
    login_cmd.add_argument("--settings", default="config/settings.json")
    login_cmd.add_argument("--url", default="")

    portal_cmd = subparsers.add_parser("assist-portal", help="Buka satu sesi portal dan prefill halaman aktif")
    portal_cmd.add_argument("--profile", default="config/profil.json")
    portal_cmd.add_argument("--settings", default="config/settings.json")
    portal_cmd.add_argument("--application-id", type=int, required=True)

    portal_queue_cmd = subparsers.add_parser(
        "assist-portal-queue", help="Proses semua DRAFT_READY_PORTAL secara berurutan"
    )
    portal_queue_cmd.add_argument("--profile", default="config/profil.json")
    portal_queue_cmd.add_argument("--settings", default="config/settings.json")
    portal_queue_cmd.add_argument("--limit", type=int, default=100)

    submitted_cmd = subparsers.add_parser(
        "mark-portal-submitted", help="Tandai portal sudah disubmit manual"
    )
    submitted_cmd.add_argument("--settings", default="config/settings.json")
    submitted_cmd.add_argument("--application-id", type=int, required=True)

    list_cmd = subparsers.add_parser("list", help="Lihat histori lowongan")
    list_cmd.add_argument("--settings", default="config/settings.json")
    list_cmd.add_argument("--limit", type=int, default=20)

    apps_cmd = subparsers.add_parser("list-applications", help="Lihat status lamaran")
    apps_cmd.add_argument("--settings", default="config/settings.json")
    apps_cmd.add_argument("--limit", type=int, default=20)

    telegram_report_cmd = subparsers.add_parser(
        "telegram-application-report",
        help="Kirim daftar dan status lamaran ke Telegram",
    )
    telegram_report_cmd.add_argument("--settings", default="config/settings.json")
    telegram_report_cmd.add_argument("--limit", type=int, default=50)

    audit_cmd = subparsers.add_parser("list-audit", help="Lihat audit trail")
    audit_cmd.add_argument("--settings", default="config/settings.json")
    audit_cmd.add_argument("--limit", type=int, default=50)

    reset_cmd = subparsers.add_parser("reset", help="Reset database dan output test")
    reset_cmd.add_argument("--settings", default="config/settings.json")
    return parser


def _load_profile_settings(
    profile_path: str,
    settings_path: str,
    mode: str | None = None,
    analysis_mode: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = load_json(profile_path)
    settings = load_json(settings_path)
    if mode:
        settings["discovery_mode"] = mode
    if analysis_mode:
        settings["analysis_mode"] = analysis_mode
    return profile, settings


def command_run(profile_path: str, settings_path: str, mode: str | None, analysis_mode: str | None) -> int:
    profile, settings = _load_profile_settings(profile_path, settings_path, mode, analysis_mode)
    stats = run_pipeline(profile, settings)
    print("\n" + build_summary(stats) + "\n")
    print("COLLECTOR")
    for item in stats.get("collectors", []):
        print(f"- {item['status']:7} | {item['found']:3} | {item['name']} | {item['message']}")
    print(f"\nReport: {stats['report_path']}")
    for item in stats["results"]:
        print(
            f"- {item['decision']:6} | {item['score']:3} | "
            f"{item.get('analysis_mode', 'ERROR'):13} | "
            f"{item.get('application_status', 'NOT_BUILT'):22} | "
            f"{item['company']} — {item['title']}"
        )
    return 0 if not stats.get("analysis_failures") else 2


def command_scheduled_run(profile_path: str, settings_path: str) -> int:
    profile, settings = _load_profile_settings(profile_path, settings_path)
    stats = run_pipeline(profile, settings)
    print(build_summary(stats))
    if settings.get("scheduler", {}).get("create_gmail_drafts", True):
        delivery = create_pending_gmail_drafts(profile, settings)
        print("\n" + build_delivery_summary(delivery))
        if settings.get("telegram_enabled", False):
            send_telegram(settings, build_delivery_summary(delivery))
        return 2 if delivery.get("failed") else 0
    return 0


def command_collect(profile_path: str, settings_path: str, mode: str | None, output: str) -> int:
    profile, settings = _load_profile_settings(profile_path, settings_path, mode)
    sources_config = load_json(str(settings.get("sources_config", "config/sources.json")))
    result = DiscoveryManager(profile, settings, sources_config).collect()
    path = export_discovery(result, output)
    print(f"Mode              : {settings.get('discovery_mode')}")
    print(f"Data mentah       : {result.raw_found}")
    print(f"Lowongan unik     : {len(result.jobs)}")
    print(f"Duplikat lintas   : {result.cross_source_duplicates}")
    print(f"Fallback dipakai  : {'Ya' if result.fallback_used else 'Tidak'}")
    for report in result.reports:
        print(f"- {report.status:7} | {report.found:3} | {report.name} | {report.message}")
    print(f"Output            : {path}")
    return 0


def command_check_sources(settings_path: str) -> int:
    settings = load_json(settings_path)
    sources_config = load_json(str(settings.get("sources_config", "config/sources.json")))
    print(f"Discovery mode: {settings.get('discovery_mode', 'live_with_fallback')}\n")
    not_ready = 0
    for source in sources_config.get("sources", []):
        if not isinstance(source, dict):
            continue
        enabled = bool(source.get("enabled", False))
        name = str(source.get("name") or source.get("type") or "Collector")
        collector_type = str(source.get("type", ""))
        status, detail = "DISABLED", "Dinonaktifkan"
        if enabled:
            status, detail = "READY", "Konfigurasi tersedia"
            if collector_type == "brave_search":
                env_name = str(source.get("api_key_env", "BRAVE_SEARCH_API_KEY"))
                if not os.getenv(env_name, "").strip():
                    status, detail = "NEEDS_KEY", f"Isi {env_name} pada .env"
            elif collector_type == "rss" and not source.get("feeds"):
                status, detail = "EMPTY", "Belum ada URL feed"
            elif collector_type in {"url_list", "csv"} and not Path(str(source.get("path", ""))).exists():
                status, detail = "MISSING", f"File tidak ditemukan: {source.get('path', '')}"
        if enabled and status not in {"READY", "NEEDS_KEY"}:
            not_ready += 1
        print(f"- {status:9} | {name} ({collector_type}) | {detail}")
    return 2 if not_ready else 0


def command_check_ai(settings_path: str) -> int:
    settings = load_json(settings_path)
    mode = str(settings.get("analysis_mode", "ai_with_fallback"))
    env_name = str(settings.get("openai_api_key_env", "OPENAI_API_KEY"))
    ready = bool(os.getenv(env_name, "").strip())
    print(f"Analysis mode : {mode}\nAI model      : {settings.get('ai_model', '')}\nAPI key       : {'READY' if ready else 'MISSING'}")
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


def command_check_scheduler(settings_path: str) -> int:
    settings = load_json(settings_path)
    checks = scheduler_readiness(settings)
    for key, status in checks:
        print(f"- {key:15}: {status}")
    return 2 if any(status not in {"READY", "DISABLED"} for _, status in checks) else 0


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
    settings = load_json(settings_path)
    try:
        code = prepare_email_approval(settings, application_id)
    except GmailDeliveryError as exc:
        print(f"Approval gagal: {exc}")
        return 2
    print("Kode approval dibuat. Periksa draft Gmail sebelum melanjutkan.")
    print(f"Kode: {code}")
    print(f"Kirim dengan: send_email.bat {application_id} {code}")
    return 0


def command_send_email(settings_path: str, application_id: int, confirmation: str) -> int:
    settings = load_json(settings_path)
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
    settings = load_json(settings_path)
    try:
        result = launch_portal_login_browser(
            settings, initial_url=url.strip() or None
        )
    except PortalAssistantError as exc:
        print(f"Portal login gagal: {exc}")
        return 2
    print("Browser login KarirLog siap.")
    print(f"Mode       : {result.get('status', '-')}")
    print(f"CDP        : {result.get('cdp_url', '-')}")
    print(f"Profile    : {result.get('user_data_dir', '-')}")
    print("Login ke portal di browser tersebut dan biarkan browser tetap terbuka.")
    return 0


def command_assist_portal_queue(
    profile_path: str, settings_path: str, limit: int
) -> int:
    profile, settings = _load_profile_settings(profile_path, settings_path)
    try:
        result = assist_portal_queue(
            profile, settings, limit=limit, interactive=True
        )
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
    if (
        settings.get("telegram_enabled", False)
        and report_cfg.get("auto_after_portal_queue", True)
    ):
        database = Database(settings["database_path"])
        try:
            rows = database.list_applications(
                max(1, int(report_cfg.get("limit", 50)))
            )
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
    settings = load_json(settings_path)
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
    settings = load_json(settings_path)
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
    settings = load_json(settings_path)
    database = Database(settings["database_path"])
    try:
        rows = database.list_applications(limit)
        for row in rows:
            external = row["gmail_message_id"] or row["gmail_draft_id"] or "-"
            print(
                f"#{row['id']:03} | {row['status']:24} | {row['apply_channel'] or '-':6} | "
                f"CV={row['selected_cv_id'] or '-'} | External={external} | "
                f"{row['company']} — {row['title']}"
            )
            if row["last_error"]:
                print(f"  Error: {row['last_error']}")
        if not rows:
            print("Belum ada lamaran.")
        return 0
    finally:
        database.close()


def command_telegram_application_report(settings_path: str, limit: int) -> int:
    settings = load_json(settings_path)
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
    settings = load_json(settings_path)
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
    settings = load_json(settings_path)
    database_path = Path(settings["database_path"])
    for candidate in (database_path, Path(str(database_path) + "-shm"), Path(str(database_path) + "-wal")):
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


def main() -> int:
    load_dotenv(override=True)
    args = make_parser().parse_args()
    commands = {
        "run": lambda: command_run(args.profile, args.settings, args.mode, args.analysis_mode),
        "scheduled-run": lambda: command_scheduled_run(args.profile, args.settings),
        "collect": lambda: command_collect(args.profile, args.settings, args.mode, args.output),
        "check-sources": lambda: command_check_sources(args.settings),
        "check-ai": lambda: command_check_ai(args.settings),
        "check-cv": lambda: command_check_cv(args.profile, args.settings),
        "check-documents": lambda: command_check_documents(args.profile, args.settings),
        "check-gmail": lambda: command_check_gmail(args.profile, args.settings),
        "check-scheduler": lambda: command_check_scheduler(args.settings),
        "create-gmail-drafts": lambda: command_create_gmail_drafts(args.profile, args.settings, args.limit),
        "approve-email": lambda: command_approve_email(args.settings, args.application_id),
        "send-email": lambda: command_send_email(args.settings, args.application_id, args.confirm),
        "portal-login": lambda: command_portal_login(args.settings, args.url),
        "assist-portal": lambda: command_assist_portal(args.profile, args.settings, args.application_id),
        "assist-portal-queue": lambda: command_assist_portal_queue(args.profile, args.settings, args.limit),
        "mark-portal-submitted": lambda: command_mark_portal_submitted(args.settings, args.application_id),
        "list": lambda: command_list(args.settings, args.limit),
        "list-applications": lambda: command_list_applications(args.settings, args.limit),
        "telegram-application-report": lambda: command_telegram_application_report(
            args.settings, args.limit
        ),
        "list-audit": lambda: command_list_audit(args.settings, args.limit),
        "reset": lambda: command_reset(args.settings),
    }
    return commands[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
