from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import secrets
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Protocol


class GmailDeliveryError(RuntimeError):
    """Raised when a Gmail operation cannot be completed safely."""


class GmailDraftService(Protocol):
    def create_draft(self, raw_message: str) -> dict[str, Any]: ...

    def send_draft(self, draft_id: str) -> dict[str, Any]: ...


@dataclass(slots=True)
class GmailOperationResult:
    status: str
    draft_id: str = ""
    message_id: str = ""
    detail: str = ""


class GoogleGmailService:
    """Thin adapter around the official Gmail API client.

    Imports are intentionally lazy so the rest of KarirLog can run without
    Google dependencies when Gmail is disabled.
    """

    def __init__(self, settings: dict[str, Any]):
        self.settings = settings
        self._service: Any | None = None

    def _build_service(self) -> Any:
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise GmailDeliveryError(
                "Dependency Gmail belum terpasang. Jalankan install_dependencies.bat."
            ) from exc

        gmail_cfg = self.settings.get("gmail", {})
        credentials_path = Path(str(gmail_cfg.get("credentials_path", "credentials.json")))
        token_path = Path(str(gmail_cfg.get("token_path", "data/secrets/gmail_token.json")))
        token_path.parent.mkdir(parents=True, exist_ok=True)
        scopes = ["https://www.googleapis.com/auth/gmail.compose"]

        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif not creds or not creds.valid:
            if not credentials_path.exists():
                raise GmailDeliveryError(
                    f"OAuth credentials tidak ditemukan: {credentials_path}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    @property
    def service(self) -> Any:
        if self._service is None:
            self._service = self._build_service()
        return self._service

    def create_draft(self, raw_message: str) -> dict[str, Any]:
        return (
            self.service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw_message}})
            .execute()
        )

    def send_draft(self, draft_id: str) -> dict[str, Any]:
        return (
            self.service.users()
            .drafts()
            .send(userId="me", body={"id": draft_id})
            .execute()
        )


def _read_required_text(path: Path, label: str) -> str:
    if not path.exists():
        raise GmailDeliveryError(f"{label} tidak ditemukan: {path}")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise GmailDeliveryError(f"{label} kosong: {path}")
    return value


def _safe_package_path(output_path: Path, relative_path: str) -> Path:
    root = output_path.resolve()
    candidate = (output_path / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise GmailDeliveryError(
            f"Path attachment keluar dari folder paket: {relative_path}"
        ) from exc
    return candidate


def _attachment_paths_from_manifest(output_path: Path) -> list[tuple[str, Path]]:
    manifest_path = output_path / "package_manifest.json"
    if not manifest_path.exists():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GmailDeliveryError(f"Manifest paket tidak dapat dibaca: {exc}") from exc

    raw_attachments = manifest.get("attachments", [])
    if not isinstance(raw_attachments, list) or not raw_attachments:
        return []
    ordered = sorted(
        (item for item in raw_attachments if isinstance(item, dict)),
        key=lambda item: int(item.get("order", 999999)),
    )
    paths: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for item in ordered:
        relative = str(item.get("path", "")).strip()
        kind = str(item.get("kind", "ATTACHMENT")).strip().upper()
        if not relative:
            continue
        path = _safe_package_path(output_path, relative)
        if path in seen:
            continue
        seen.add(path)
        paths.append((kind, path))
    return paths


def _legacy_attachment_paths(
    output_path: Path, application: dict[str, Any]
) -> list[tuple[str, Path]]:
    attachments_dir = output_path / "attachments"
    package_files = (
        sorted(
            (path for path in attachments_dir.iterdir() if path.is_file()),
            key=lambda path: path.name.lower(),
        )
        if attachments_dir.exists()
        else []
    )
    selected_cv = Path(str(application.get("selected_cv_path", "")))
    selected_name = selected_cv.name.lower() if selected_cv.name else ""
    if package_files:
        package_files.sort(
            key=lambda path: (0 if path.name.lower() == selected_name else 1, path.name.lower())
        )
        return [
            ("CV" if index == 0 else "ATTACHMENT", path)
            for index, path in enumerate(package_files)
        ]
    return [("CV", selected_cv)] if selected_cv else []


def _resolve_attachment_paths(
    output_path: Path, application: dict[str, Any]
) -> list[tuple[str, Path]]:
    paths = _attachment_paths_from_manifest(output_path)
    if not paths:
        paths = _legacy_attachment_paths(output_path, application)
    if not paths:
        raise GmailDeliveryError("Tidak ada attachment pada paket lamaran")
    if paths[0][0] != "CV":
        raise GmailDeliveryError("Attachment pertama pada manifest wajib berjenis CV")
    for _, path in paths:
        if not path.exists() or not path.is_file():
            raise GmailDeliveryError(f"Attachment tidak ditemukan: {path}")
    return paths


def build_raw_message(application: dict[str, Any], profile: dict[str, Any]) -> str:
    output_path = Path(str(application.get("output_path", "")))
    if not output_path.exists():
        raise GmailDeliveryError(f"Folder paket tidak ditemukan: {output_path}")

    recipient = str(application.get("recipient", "")).strip()
    sender = str(profile.get("email", "")).strip()
    if not recipient or "@" not in recipient:
        raise GmailDeliveryError("Email penerima belum valid")
    if not sender or "@" not in sender:
        raise GmailDeliveryError("Email pengirim belum diisi pada config/profil.json")

    subject = _read_required_text(output_path / "email_subject.txt", "Subject email")
    body = _read_required_text(output_path / "email_body.txt", "Body email")

    message = EmailMessage()
    message["To"] = recipient
    message["From"] = sender
    message["Subject"] = subject
    message.set_content(body)

    for _, attachment_path in _resolve_attachment_paths(output_path, application):
        mime_type, _ = mimetypes.guess_type(attachment_path.name)
        if mime_type and "/" in mime_type:
            maintype, subtype = mime_type.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"
        message.add_attachment(
            attachment_path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=attachment_path.name,
        )
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


def create_gmail_draft(
    application: dict[str, Any],
    profile: dict[str, Any],
    service: GmailDraftService,
) -> GmailOperationResult:
    if str(application.get("apply_channel", "")) != "EMAIL":
        raise GmailDeliveryError("Application bukan channel EMAIL")
    if str(application.get("status", "")) not in {
        "DRAFT_READY_EMAIL",
        "GMAIL_DRAFT_FAILED",
    }:
        raise GmailDeliveryError(
            f"Status tidak boleh dibuatkan draft Gmail: {application.get('status')}"
        )
    raw = build_raw_message(application, profile)
    response = service.create_draft(raw)
    draft_id = str(response.get("id", ""))
    message_id = str((response.get("message") or {}).get("id", ""))
    if not draft_id:
        raise GmailDeliveryError("Gmail API tidak mengembalikan draft ID")
    return GmailOperationResult(
        status="GMAIL_DRAFT_CREATED",
        draft_id=draft_id,
        message_id=message_id,
        detail="Draft Gmail berhasil dibuat",
    )


def issue_approval_code(application_id: int) -> tuple[str, str]:
    token = secrets.token_hex(3).upper()
    plaintext = f"KLG-{application_id:04d}-{token}"
    digest = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
    return plaintext, digest


def validate_approval_code(plaintext: str, expected_hash: str) -> bool:
    actual = hashlib.sha256(plaintext.strip().encode("utf-8")).hexdigest()
    return bool(expected_hash) and secrets.compare_digest(actual, expected_hash)


def send_approved_gmail_draft(
    application: dict[str, Any],
    confirmation_code: str,
    service: GmailDraftService,
) -> GmailOperationResult:
    if str(application.get("status", "")) != "EMAIL_APPROVAL_PENDING":
        raise GmailDeliveryError("Email belum berada pada status approval pending")
    if not validate_approval_code(
        confirmation_code, str(application.get("approval_code_hash", ""))
    ):
        raise GmailDeliveryError("Kode persetujuan tidak cocok")
    draft_id = str(application.get("gmail_draft_id", ""))
    if not draft_id:
        raise GmailDeliveryError("Draft Gmail belum tersedia")
    response = service.send_draft(draft_id)
    message_id = str(response.get("id", ""))
    if not message_id:
        raise GmailDeliveryError("Gmail API tidak mengembalikan message ID")
    return GmailOperationResult(
        status="EMAIL_SENT",
        draft_id=draft_id,
        message_id=message_id,
        detail="Email berhasil dikirim setelah persetujuan eksplisit",
    )


def gmail_readiness(settings: dict[str, Any], profile: dict[str, Any]) -> list[tuple[str, str]]:
    cfg = settings.get("gmail", {})
    checks: list[tuple[str, str]] = []
    checks.append(("enabled", "READY" if cfg.get("enabled", False) else "DISABLED"))
    credentials = Path(str(cfg.get("credentials_path", "credentials.json")))
    checks.append(("credentials", "READY" if credentials.exists() else "MISSING"))
    email = str(profile.get("email", "")).strip()
    checks.append(("profile_email", "READY" if "@" in email else "MISSING"))
    checks.append(("send_mode", str(cfg.get("send_mode", "draft_only"))))
    return checks
