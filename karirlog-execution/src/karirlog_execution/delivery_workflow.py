from __future__ import annotations

from typing import Any

from .database import Database
from .gmail_delivery import (
    GmailDeliveryError,
    GoogleGmailService,
    create_gmail_draft,
    issue_approval_code,
    send_approved_gmail_draft,
)
from .portal_assistant import (
    PortalAssistantError,
    build_prefill_plan,
    run_portal_assistant,
)
from .portal_queue import run_external_portal_queue


def create_pending_gmail_drafts(
    profile: dict[str, Any],
    settings: dict[str, Any],
    *,
    service: Any | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    database = Database(settings["database_path"])
    result = {"created": 0, "failed": 0, "skipped": 0, "items": []}
    try:
        gmail_cfg = settings.get("gmail", {})
        configured_limit = max(1, int(gmail_cfg.get("max_drafts_per_run", 10)))
        limit = min(limit, configured_limit)
        if not gmail_cfg.get("enabled", False):
            result["skipped"] = len(database.list_email_queue(limit))
            result["message"] = "Gmail dinonaktifkan"
            return result
        gmail_service = service or GoogleGmailService(settings)
        for application in database.list_email_queue(limit):
            app_id = int(application["id"])
            try:
                operation = create_gmail_draft(application, profile, gmail_service)
                database.update_delivery(
                    app_id,
                    status=operation.status,
                    gmail_draft_id=operation.draft_id,
                    gmail_message_id=operation.message_id,
                    last_error="",
                )
                database.record_event(
                    "GMAIL_DRAFT_CREATED",
                    application_id=app_id,
                    job_id=int(application["job_id"]),
                    status=operation.status,
                    detail=operation.detail,
                    metadata={"draft_id": operation.draft_id},
                )
                result["created"] += 1
                result["items"].append(
                    {"application_id": app_id, "status": operation.status}
                )
            except GmailDeliveryError as exc:
                database.update_delivery(
                    app_id, status="GMAIL_DRAFT_FAILED", last_error=str(exc)
                )
                database.record_event(
                    "GMAIL_DRAFT_FAILED",
                    application_id=app_id,
                    job_id=int(application["job_id"]),
                    status="GMAIL_DRAFT_FAILED",
                    detail=str(exc),
                )
                result["failed"] += 1
                result["items"].append(
                    {
                        "application_id": app_id,
                        "status": "GMAIL_DRAFT_FAILED",
                        "error": str(exc),
                    }
                )
        return result
    finally:
        database.close()


def prepare_email_approval(settings: dict[str, Any], application_id: int) -> str:
    database = Database(settings["database_path"])
    try:
        application = database.get_application(application_id)
        if not application:
            raise GmailDeliveryError("Application tidak ditemukan")
        if str(application.get("status", "")) != "GMAIL_DRAFT_CREATED":
            raise GmailDeliveryError(
                "Approval hanya dapat dibuat untuk status GMAIL_DRAFT_CREATED"
            )
        code, digest = issue_approval_code(application_id)
        database.update_delivery(
            application_id,
            status="EMAIL_APPROVAL_PENDING",
            approval_code_hash=digest,
            approved=True,
            last_error="",
        )
        database.record_event(
            "EMAIL_APPROVAL_ISSUED",
            application_id=application_id,
            job_id=int(application["job_id"]),
            status="EMAIL_APPROVAL_PENDING",
            detail="Kode approval dibuat. Kode plaintext tidak disimpan.",
        )
        return code
    finally:
        database.close()


def send_email_with_approval(
    settings: dict[str, Any],
    application_id: int,
    confirmation_code: str,
    *,
    service: Any | None = None,
) -> dict[str, Any]:
    database = Database(settings["database_path"])
    try:
        application = database.get_application(application_id)
        if not application:
            raise GmailDeliveryError("Application tidak ditemukan")
        gmail_cfg = settings.get("gmail", {})
        if str(gmail_cfg.get("send_mode", "draft_only")) != "approved_send":
            raise GmailDeliveryError(
                "gmail.send_mode masih draft_only. Ubah ke approved_send untuk mengirim."
            )
        from datetime import datetime, timezone

        approved_at = str(application.get("approved_at", "")).strip()
        if not approved_at:
            raise GmailDeliveryError("Timestamp approval tidak tersedia")
        approved_dt = datetime.fromisoformat(approved_at.replace(" ", "T") + "+00:00")
        age_minutes = (datetime.now(timezone.utc) - approved_dt).total_seconds() / 60
        ttl = max(1, int(gmail_cfg.get("approval_ttl_minutes", 30)))
        if age_minutes > ttl:
            raise GmailDeliveryError("Kode approval sudah kedaluwarsa")
        daily_limit = max(1, int(gmail_cfg.get("max_sends_per_day", 5)))
        if database.count_events_today("EMAIL_SENT") >= daily_limit:
            raise GmailDeliveryError("Batas pengiriman email harian KarirLog telah tercapai")

        gmail_service = service or GoogleGmailService(settings)
        operation = send_approved_gmail_draft(
            application, confirmation_code, gmail_service
        )
        database.update_delivery(
            application_id,
            status=operation.status,
            gmail_message_id=operation.message_id,
            sent=True,
            last_error="",
        )
        database.record_event(
            "EMAIL_SENT",
            application_id=application_id,
            job_id=int(application["job_id"]),
            status=operation.status,
            detail=operation.detail,
            metadata={"message_id": operation.message_id},
        )
        return {
            "application_id": application_id,
            "status": operation.status,
            "message_id": operation.message_id,
        }
    except GmailDeliveryError as exc:
        if database.get_application(application_id):
            database.update_delivery(
                application_id,
                status=str(database.get_application(application_id).get("status", "")),
                last_error=str(exc),
            )
            database.record_event(
                "EMAIL_SEND_REJECTED",
                application_id=application_id,
                status="REJECTED",
                detail=str(exc),
            )
        raise
    finally:
        database.close()


def assist_portal_application(
    profile: dict[str, Any],
    settings: dict[str, Any],
    application_id: int,
    *,
    interactive: bool = True,
    runner: Any | None = None,
) -> dict[str, Any]:
    database = Database(settings["database_path"])
    try:
        application = database.get_application(application_id)
        if not application:
            raise PortalAssistantError("Application tidak ditemukan")
        if str(application.get("status", "")) not in {
            "DRAFT_READY_PORTAL",
            "PORTAL_ASSIST_FAILED",
            "PORTAL_REVIEW_REQUIRED",
        }:
            raise PortalAssistantError(
                f"Status tidak dapat diproses portal assistant: {application.get('status')}"
            )
        plan = build_prefill_plan(application, profile)
        execute = runner or run_portal_assistant
        try:
            report = execute(plan, settings, interactive=interactive)
        except PortalAssistantError as exc:
            database.update_delivery(
                application_id, status="PORTAL_ASSIST_FAILED", last_error=str(exc)
            )
            database.record_event(
                "PORTAL_ASSIST_FAILED",
                application_id=application_id,
                job_id=int(application["job_id"]),
                status="PORTAL_ASSIST_FAILED",
                detail=str(exc),
            )
            raise
        result_status = str(report.get("status", "PORTAL_REVIEW_REQUIRED"))
        if result_status not in {
            "DRAFT_READY_PORTAL",
            "PORTAL_REVIEW_REQUIRED",
            "PORTAL_SUBMITTED",
        }:
            result_status = "PORTAL_REVIEW_REQUIRED"

        database.update_delivery(
            application_id,
            status=result_status,
            portal_report_path=str(report.get("report_path", "")),
            last_error="",
            sent=result_status == "PORTAL_SUBMITTED",
        )
        if result_status == "PORTAL_SUBMITTED":
            event_type = "PORTAL_SUBMITTED_MANUAL"
            detail = "Pengguna mengonfirmasi lamaran sudah disubmit manual dari sesi Portal Assistant."
        elif result_status == "DRAFT_READY_PORTAL":
            event_type = "PORTAL_ASSIST_CANCELLED"
            detail = "Sesi Portal Assistant dibatalkan; application dikembalikan ke antrean portal."
        else:
            event_type = "PORTAL_PREFILLED"
            detail = "Browser dibuka; pengguna dapat login, membuka form, dan mengisi/meninjau tanpa submit otomatis."
        database.record_event(
            event_type,
            application_id=application_id,
            job_id=int(application["job_id"]),
            status=result_status,
            detail=detail,
            metadata={
                "filled": report.get("filled", []),
                "warnings": report.get("warnings", []),
            },
        )
        return report
    finally:
        database.close()

def assist_portal_queue(
    profile: dict[str, Any],
    settings: dict[str, Any],
    *,
    limit: int = 100,
    interactive: bool = True,
    runner: Any | None = None,
) -> dict[str, Any]:
    """Process all pending portal applications in one reusable browser session."""
    database = Database(settings["database_path"])
    summary: dict[str, Any] = {
        "queued": 0,
        "processed": 0,
        "submitted": 0,
        "review": 0,
        "skipped": 0,
        "failed": 0,
        "items": [],
    }
    try:
        applications = database.list_portal_queue(max(1, int(limit)))
        summary["queued"] = len(applications)
        if not applications:
            return summary

        plans = []
        app_by_id: dict[int, dict[str, Any]] = {}
        for application in applications:
            app_id = int(application["id"])
            try:
                plan = build_prefill_plan(application, profile)
            except PortalAssistantError as exc:
                database.update_delivery(
                    app_id, status="PORTAL_ASSIST_FAILED", last_error=str(exc)
                )
                database.record_event(
                    "PORTAL_ASSIST_FAILED",
                    application_id=app_id,
                    job_id=int(application["job_id"]),
                    status="PORTAL_ASSIST_FAILED",
                    detail=str(exc),
                )
                summary["failed"] += 1
                summary["items"].append(
                    {
                        "application_id": app_id,
                        "status": "PORTAL_ASSIST_FAILED",
                        "error": str(exc),
                    }
                )
                continue
            plans.append(plan)
            app_by_id[app_id] = application

        execute = runner or run_external_portal_queue
        for report in execute(plans, settings, interactive=interactive):
            app_id = int(report.get("application_id", 0))
            application = app_by_id.get(app_id)
            if application is None:
                continue
            status = str(report.get("status", "PORTAL_REVIEW_REQUIRED"))
            if status not in {
                "DRAFT_READY_PORTAL",
                "PORTAL_REVIEW_REQUIRED",
                "PORTAL_SUBMITTED",
                "PORTAL_ASSIST_FAILED",
            }:
                status = "PORTAL_REVIEW_REQUIRED"

            database.update_delivery(
                app_id,
                status=status,
                portal_report_path=str(report.get("report_path", "")),
                last_error=(
                    "; ".join(str(item) for item in report.get("warnings", []))
                    if status == "PORTAL_ASSIST_FAILED"
                    else ""
                ),
                sent=status == "PORTAL_SUBMITTED",
            )
            if status == "PORTAL_SUBMITTED":
                event_type = "PORTAL_SUBMITTED_MANUAL"
                detail = "Pengguna mengonfirmasi submit manual dari antrean Portal Assistant."
                summary["submitted"] += 1
            elif status == "PORTAL_REVIEW_REQUIRED":
                event_type = "PORTAL_PREFILLED"
                detail = "Form ditinjau melalui antrean; submit belum dikonfirmasi."
                summary["review"] += 1
            elif status == "PORTAL_ASSIST_FAILED":
                event_type = "PORTAL_ASSIST_FAILED"
                detail = "; ".join(
                    str(item) for item in report.get("warnings", [])
                ) or "Portal Assistant gagal."
                summary["failed"] += 1
            else:
                event_type = "PORTAL_ASSIST_SKIPPED"
                detail = "Application dilewati dan tetap berada dalam antrean portal."
                summary["skipped"] += 1

            database.record_event(
                event_type,
                application_id=app_id,
                job_id=int(application["job_id"]),
                status=status,
                detail=detail,
                metadata={
                    "filled": report.get("filled", []),
                    "warnings": report.get("warnings", []),
                    "queue": True,
                },
            )
            summary["processed"] += 1
            summary["items"].append(
                {"application_id": app_id, "status": status}
            )
        return summary
    finally:
        database.close()

