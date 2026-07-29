from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from .cv_selector import select_cv
from .document_library import select_documents
from .models import (
    AnalysisResult,
    ApplicationPackageResult,
    DocumentSelection,
    Job,
)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    return cleaned.strip("_")[:80] or "job"


def resolve_apply_destination(job: Job) -> tuple[str, str, list[str]]:
    email = job.apply_email.strip()
    if email and EMAIL_RE.match(email):
        return "EMAIL", email, []
    warnings: list[str] = []
    if email:
        warnings.append(f"Email apply tidak valid: {email}")
    if job.url.strip().lower().startswith(("http://", "https://")):
        return "PORTAL", job.url.strip(), warnings
    warnings.append("Tidak ada email atau URL apply yang valid")
    return "UNAVAILABLE", "", warnings


def _write_text(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unique_destination(folder: Path, filename: str, used_names: set[str]) -> Path:
    source_name = Path(filename).name
    stem = Path(source_name).stem
    suffix = Path(source_name).suffix
    candidate = source_name
    index = 2
    while candidate.lower() in used_names or (folder / candidate).exists():
        candidate = f"{stem}_{index}{suffix}"
        index += 1
    used_names.add(candidate.lower())
    return folder / candidate


def _copy_selected_documents(
    folder: Path, selection: DocumentSelection
) -> tuple[list[str], str, list[str]]:
    attachments_dir = folder / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    attached_files: list[str] = []
    attached_cv_path = ""
    errors: list[str] = []

    for index, item in enumerate(selection.selected_files):
        source = Path(str(item.get("source_path", "")))
        if not source.exists() or not source.is_file():
            errors.append(f"File terpilih tidak ditemukan saat copy: {source}")
            continue
        destination = _unique_destination(attachments_dir, source.name, used_names)
        try:
            shutil.copy2(source, destination)
        except OSError as exc:
            errors.append(f"Gagal menyalin {source.name}: {exc}")
            continue
        item["package_path"] = destination.relative_to(folder).as_posix()
        item["package_file_path"] = str(destination)
        attached_files.append(str(destination))
        if index == 0 and str(item.get("kind")) == "CV":
            attached_cv_path = str(destination)

    return attached_files, attached_cv_path, errors


def _package_manifest(folder: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.name == "package_manifest.json":
            continue
        files.append(
            {
                "path": path.relative_to(folder).as_posix(),
                "size": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )

    document_selection = metadata.get("document_selection", {})
    selected_documents: list[dict[str, Any]] = []
    if isinstance(document_selection, dict):
        cv = document_selection.get("selected_cv")
        if isinstance(cv, dict) and cv.get("package_path"):
            selected_documents.append(cv)
        for key in ("automatic_attachments", "selected_supporting_documents"):
            items = document_selection.get(key, [])
            if isinstance(items, list):
                selected_documents.extend(
                    item
                    for item in items
                    if isinstance(item, dict) and item.get("package_path")
                )

    attachments = [
        {
            "order": index + 1,
            "kind": str(item.get("kind", "ATTACHMENT")),
            "document_type": str(item.get("document_type", "")),
            "name": str(item.get("name", "")),
            "path": str(item.get("package_path", "")),
            "size": int(item.get("size", 0)),
            "sha256": str(item.get("sha256", "")),
        }
        for index, item in enumerate(selected_documents)
    ]
    return {
        "package_version": "1.1",
        "status": metadata["status"],
        "job_id": metadata["job_id"],
        "apply_channel": metadata["apply_channel"],
        "recipient": metadata["recipient"],
        "selected_cv_id": metadata["cv_selection"]["cv_id"],
        "attachment_order": [item["path"] for item in attachments],
        "attachments": attachments,
        "total_attachment_count": len(attachments),
        "total_attachment_size_bytes": sum(item["size"] for item in attachments),
        "files": files,
    }


def _build_cover_letter(
    job: Job,
    result: AnalysisResult,
    profile: dict[str, Any],
) -> str:
    full_name = str(profile.get("full_name", "Pelamar")).strip() or "Pelamar"
    experience = str(profile.get("experience_summary", "")).strip()
    matched = result.matched_skills[:6]
    transferable = result.transferable_strengths[:4]

    evidence_parts: list[str] = []
    if matched:
        evidence_parts.append("kompetensi yang relevan seperti " + ", ".join(matched))
    if transferable:
        evidence_parts.append("pengalaman transferable dalam " + ", ".join(transferable))
    evidence_text = " serta ".join(evidence_parts) or "area yang relevan dengan kebutuhan posisi"

    experience_paragraph = f"\n{experience}\n" if experience else "\n"
    return f"""Yth. Tim Rekrutmen {job.company},

Saya {full_name} bermaksud melamar posisi {job.title}. Ketertarikan saya didasarkan pada kecocokan antara kebutuhan posisi dan {evidence_text}.
{experience_paragraph}
Saya hanya mencantumkan pengalaman dan kemampuan yang benar-benar saya miliki. Saya siap menjelaskan proses belajar, proyek, dan pengalaman relevan secara lebih rinci dalam proses seleksi.

Terima kasih atas waktu dan pertimbangannya.

Hormat saya,
{full_name}
"""


def _build_email_body(
    job: Job,
    result: AnalysisResult,
    profile: dict[str, Any],
    attachment_count: int,
) -> str:
    full_name = str(profile.get("full_name", "Pelamar")).strip() or "Pelamar"
    matched = ", ".join(result.matched_skills[:5]) or "area yang relevan dengan posisi"
    attachment_text = (
        "CV dan dokumen pendukung yang relevan telah saya lampirkan"
        if attachment_count > 1
        else "CV saya lampirkan"
    )
    return f"""Yth. Tim Rekrutmen {job.company},

Perkenalkan, saya {full_name}. Saya mengirimkan lamaran untuk posisi {job.title}.

Saya tertarik pada posisi ini karena terdapat kecocokan pada {matched}. {attachment_text} untuk dipertimbangkan.

Saya siap mengikuti proses seleksi dan berdiskusi lebih lanjut mengenai pengalaman serta kemampuan yang relevan.

Terima kasih.

Hormat saya,
{full_name}
"""


def build_application(
    output_root: str | Path,
    job_id: int,
    job: Job,
    result: AnalysisResult,
    profile: dict[str, Any],
    settings: dict[str, Any],
) -> ApplicationPackageResult:
    folder = Path(output_root) / f"job_{job_id}_{safe_name(job.company)}_{safe_name(job.title)}"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=True)

    cv_selection = select_cv(job, result, profile, settings)
    document_selection = select_documents(
        job, result, cv_selection, profile, settings
    )
    apply_channel, recipient, destination_warnings = resolve_apply_destination(job)
    warnings = list(destination_warnings)

    if not cv_selection.ready:
        status = cv_selection.status
    elif not document_selection.ready:
        status = document_selection.status
    elif apply_channel == "UNAVAILABLE":
        status = "BLOCKED_DESTINATION"
    elif apply_channel == "EMAIL":
        status = "DRAFT_READY_EMAIL"
    else:
        status = "DRAFT_READY_PORTAL"

    attached_files: list[str] = []
    attached_cv_path = ""
    if cv_selection.ready and bool(settings.get("copy_selected_cv_to_package", True)):
        attached_files, attached_cv_path, copy_errors = _copy_selected_documents(
            folder, document_selection
        )
        if copy_errors:
            warnings.extend(copy_errors)
            document_selection.status = "BLOCKED_INVALID_FILE"
            document_selection.warnings.extend(copy_errors)
            status = "BLOCKED_INVALID_FILE"

    full_name = str(profile.get("full_name", "Pelamar")).strip() or "Pelamar"
    _write_text(folder / "cover_letter.txt", _build_cover_letter(job, result, profile))
    _write_text(folder / "email_subject.txt", f"Lamaran {job.title} - {full_name}")
    _write_text(
        folder / "email_body.txt",
        _build_email_body(job, result, profile, len(attached_files)),
    )
    (folder / "analysis.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (folder / "cv_selection.json").write_text(
        json.dumps(cv_selection.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (folder / "document_selection.json").write_text(
        json.dumps(document_selection.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    selected_names = [Path(path).name for path in attached_files]
    review_text = [
        "KARIRLOG APPLICATION PACKAGE V1.1",
        "",
        f"Status             : {status}",
        f"Apply channel      : {apply_channel}",
        f"Recipient          : {recipient or '-'}",
        f"Document profile   : {document_selection.profile_id or '-'}",
        f"CV                 : {cv_selection.label or '-'}",
        f"CV status          : {cv_selection.status}",
        f"CV score           : {cv_selection.score}",
        f"Attachment count   : {len(attached_files)}",
        f"Attachment size    : {document_selection.total_size_bytes} byte",
        "",
        "DAFTAR LAMPIRAN (URUTAN GMAIL):",
    ]
    review_text.extend(
        f"{index}. {name}" for index, name in enumerate(selected_names, start=1)
    )
    if not selected_names:
        review_text.append("- Belum ada file yang siap dilampirkan")
    review_text.extend(
        [
            "",
            "Paket siap diproses oleh Gmail Draft atau Portal Assistant hanya jika status DRAFT_READY. Pengiriman email dan submit portal tetap memerlukan persetujuan eksplisit.",
        ]
    )
    all_warnings = (
        cv_selection.warnings + document_selection.warnings + warnings
    )
    if all_warnings:
        review_text.extend(["", "PERINGATAN:"])
        review_text.extend(f"- {item}" for item in all_warnings)
    _write_text(folder / "README_REVIEW.txt", "\n".join(review_text))

    metadata = {
        "package_version": "1.1",
        "job_id": job_id,
        "title": job.title,
        "company": job.company,
        "apply_email": job.apply_email,
        "url": job.url,
        "source": job.source,
        "location": job.location,
        "posted_at": job.posted_at,
        "employment_type": job.employment_type,
        "salary": job.salary,
        "remote": job.remote,
        "score": result.score,
        "decision": result.decision,
        "analysis_mode": result.analysis_mode,
        "provider": result.provider,
        "model": result.model,
        "confidence": result.confidence,
        "summary": result.summary,
        "seniority_level": result.seniority_level,
        "estimated_years_required": result.estimated_years_required,
        "matched_skills": result.matched_skills,
        "missing_required": result.missing_required,
        "red_flags": result.red_flags,
        "apply_channel": apply_channel,
        "recipient": recipient,
        "cv_selection": cv_selection.to_dict(),
        "document_selection": document_selection.to_dict(),
        "attached_cv_path": attached_cv_path,
        "attached_files": attached_files,
        "status": status,
        "warnings": all_warnings,
    }
    (folder / "application.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manifest = _package_manifest(folder, metadata)
    manifest_path = folder / "package_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return ApplicationPackageResult(
        status=status,
        output_path=str(folder),
        apply_channel=apply_channel,
        recipient=recipient,
        selection=cv_selection,
        document_selection=document_selection,
        manifest_path=str(manifest_path),
        attached_cv_path=attached_cv_path,
        attached_files=attached_files,
        warnings=warnings,
    )
