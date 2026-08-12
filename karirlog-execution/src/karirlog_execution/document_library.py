from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .config import load_json
from .cv_selector import get_library_profile, load_cv_library, normalize
from .models import AnalysisResult, CVSelection, DocumentSelection, Job
from .paths import resolve_config_path

DEFAULT_RULES: dict[str, Any] = {
    "version": 1,
    "document_types": {
        "ijazah": {
            "file_keywords": ["ijazah", "diploma", "degree_certificate", "degree certificate"],
            "requirement_keywords": [
                "lampirkan ijazah",
                "sertakan ijazah",
                "unggah ijazah",
                "upload ijazah",
                "attach diploma",
                "upload diploma",
                "attach degree certificate",
                "upload degree certificate",
            ],
        },
        "transkrip": {
            "file_keywords": ["transkrip", "transcript", "academic_transcript", "academic transcript"],
            "requirement_keywords": [
                "lampirkan transkrip",
                "sertakan transkrip",
                "unggah transkrip",
                "upload transkrip",
                "attach transcript",
                "upload transcript",
                "academic transcript required",
            ],
        },
        "sertifikat": {
            "file_keywords": ["sertifikat", "certificate", "certification"],
            "requirement_keywords": [
                "lampirkan sertifikat",
                "sertakan sertifikat",
                "unggah sertifikat",
                "attach certificate",
                "upload certificate",
                "certificate attachment required",
            ],
        },
        "portfolio": {
            "file_keywords": ["portfolio", "portofolio", "project_sample", "project sample"],
            "requirement_keywords": [
                "lampirkan portfolio",
                "lampirkan portofolio",
                "sertakan portfolio",
                "sertakan portofolio",
                "upload portfolio",
                "attach portfolio",
                "portfolio required",
                "portfolio is required",
            ],
        },
    },
    "sensitive_keywords": [
        "ktp",
        "kartu_tanda_penduduk",
        "kartu tanda penduduk",
        "kk",
        "kartu_keluarga",
        "kartu keluarga",
        "npwp",
        "passport",
        "paspor",
        "bank_account",
        "bank account",
        "rekening",
        "buku_rekening",
        "akta_kelahiran",
        "akta kelahiran",
        "medical",
        "medis",
    ],
}


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def load_document_rules(settings: dict[str, Any]) -> dict[str, Any]:
    path_text = str(settings.get("document_rules_config", "config/document_rules.json")).strip()
    path = resolve_config_path(path_text, settings) if path_text else None
    if path and path.exists():
        data = load_json(path)
        if isinstance(data.get("document_types", {}), dict):
            return data
    return DEFAULT_RULES


def _is_hidden_or_temporary(path: Path) -> bool:
    name = path.name.lower()
    return (
        name.startswith(".")
        or name.startswith("~$")
        or name.endswith(".tmp")
        or name.endswith(".temp")
        or name.endswith("~")
    )


def _allowed_extensions(settings: dict[str, Any]) -> set[str]:
    return {
        str(item).lower()
        for item in settings.get(
            "allowed_attachment_extensions",
            [".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg"],
        )
        if str(item).strip()
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_document_file(
    path: Path, settings: dict[str, Any], kind: str
) -> tuple[dict[str, Any] | None, str]:
    if _is_hidden_or_temporary(path):
        return None, "TEMPORARY_OR_HIDDEN"
    if not path.is_file():
        return None, "NOT_A_FILE"
    if path.suffix.lower() not in _allowed_extensions(settings):
        return None, "EXTENSION_NOT_ALLOWED"

    try:
        size = path.stat().st_size
    except OSError:
        return None, "FILE_NOT_READABLE"
    min_size = max(1, _int(settings.get("min_attachment_size_bytes", 1), 1))
    max_size = max(1.0, _float(settings.get("max_attachment_size_mb", 10), 10.0)) * 1024 * 1024
    if size < min_size:
        return None, "FILE_EMPTY_OR_TOO_SMALL"
    if size > max_size:
        return None, "FILE_TOO_LARGE"
    try:
        digest = _sha256(path)
    except OSError:
        return None, "FILE_NOT_READABLE"
    return (
        {
            "kind": kind,
            "name": path.name,
            "source_path": str(path),
            "size": size,
            "sha256": digest,
            "document_type": "",
            "selection_reason": "",
            "sensitive": False,
            "package_path": "",
        },
        "",
    )


def _folder_files(folder_text: str) -> list[Path]:
    if not folder_text:
        return []
    folder = Path(folder_text)
    if not folder.exists() or not folder.is_dir():
        return []

    def sort_key(path: Path) -> tuple[int, str]:
        normalized_name = normalize(path.stem.replace("_", " ").replace("-", " "))
        duplicate_hint = int(
            normalized_name.startswith(("copy ", "copy of ", "salinan "))
            or " duplicate " in f" {normalized_name} "
        )
        return duplicate_hint, path.name.lower()

    return sorted(
        (path for path in folder.iterdir() if path.is_file() and not _is_hidden_or_temporary(path)),
        key=sort_key,
    )


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = normalize(text)
    normalized_phrase = normalize(phrase)
    return bool(normalized_phrase) and normalized_phrase in normalized_text


def _is_sensitive(path: Path, rules: dict[str, Any]) -> bool:
    filename = normalize(path.stem.replace("_", " ").replace("-", " "))
    return any(
        _contains_phrase(filename, keyword)
        for keyword in _strings(rules.get("sensitive_keywords", []))
    )


def _classify_supporting_document(
    path: Path, rules: dict[str, Any]
) -> str:
    filename = normalize(path.stem.replace("_", " ").replace("-", " "))
    document_types = rules.get("document_types", {})
    if not isinstance(document_types, dict):
        return ""
    for document_type, definition in document_types.items():
        if not isinstance(definition, dict):
            continue
        for keyword in _strings(definition.get("file_keywords", [])):
            if _contains_phrase(filename, keyword):
                return str(document_type)
    return ""


def _required_document_types(
    job: Job, result: AnalysisResult, rules: dict[str, Any]
) -> list[str]:
    # Only explicit document-request text is considered. Skill mentions such as
    # "SAP certification preferred" must not automatically send a certificate.
    requirement_text = " ".join(
        [
            job.description,
            *result.required_requirements,
            *result.missing_required,
        ]
    )
    required: list[str] = []
    document_types = rules.get("document_types", {})
    if not isinstance(document_types, dict):
        return required
    for document_type, definition in document_types.items():
        if not isinstance(definition, dict):
            continue
        keywords = _strings(definition.get("requirement_keywords", []))
        if any(_contains_phrase(requirement_text, keyword) for keyword in keywords):
            required.append(str(document_type))
    return sorted(set(required))


def _reject(
    path: Path,
    kind: str,
    reason: str,
    *,
    document_type: str = "",
    sensitive: bool = False,
) -> dict[str, Any]:
    size = path.stat().st_size if path.exists() and path.is_file() else 0
    return {
        "kind": kind,
        "name": path.name,
        "source_path": str(path),
        "size": size,
        "sha256": "",
        "document_type": document_type,
        "reason": reason,
        "sensitive": sensitive,
    }


def _profile_folders(entry: dict[str, Any], profile_id: str) -> tuple[str, str]:
    attachment_folder = str(entry.get("attachment_folder", "")).strip()
    supporting_folder = str(entry.get("supporting_document_folder", "")).strip()
    if not attachment_folder:
        attachment_folder = f"documents/attachments/{profile_id}"
    if not supporting_folder:
        supporting_folder = f"documents/supporting_documents/{profile_id}"
    return attachment_folder, supporting_folder


def select_documents(
    job: Job,
    result: AnalysisResult,
    cv_selection: CVSelection,
    profile: dict[str, Any],
    settings: dict[str, Any],
) -> DocumentSelection:
    selection = DocumentSelection(
        status=cv_selection.status if not cv_selection.ready else "READY",
        profile_id=cv_selection.cv_id,
    )
    if not cv_selection.ready:
        selection.warnings.extend(cv_selection.warnings)
        return selection

    entry = get_library_profile(cv_selection.cv_id, profile, settings)
    if entry is None:
        selection.status = "REVIEW_DOCUMENT"
        selection.warnings.append(
            f"Profil dokumen tidak ditemukan untuk CV ID {cv_selection.cv_id}"
        )
        return selection

    rules = load_document_rules(settings)
    attachment_folder, supporting_folder = _profile_folders(entry, cv_selection.cv_id)
    attachment_folder = str(resolve_config_path(attachment_folder, settings))
    supporting_folder = str(resolve_config_path(supporting_folder, settings))
    cv_path = Path(cv_selection.source_path)
    selected_cv = {
        "kind": "CV",
        "name": cv_path.name,
        "source_path": str(cv_path),
        "size": cv_selection.file_size,
        "sha256": cv_selection.sha256,
        "document_type": "cv",
        "selection_reason": "CV terpilih dari profile yang cocok dengan lowongan",
        "sensitive": False,
        "package_path": "",
    }
    selection.selected_cv = selected_cv
    seen_hashes: dict[str, str] = {cv_selection.sha256: str(cv_path)}

    for path in _folder_files(attachment_folder):
        document, rejection_reason = _validate_document_file(path, settings, "ATTACHMENT")
        if document is None:
            selection.rejected_files.append(
                _reject(path, "ATTACHMENT", rejection_reason)
            )
            continue
        digest = str(document["sha256"])
        if digest in seen_hashes:
            selection.duplicate_files.append(
                {
                    **document,
                    "duplicate_of": seen_hashes[digest],
                    "reason": "DUPLICATE_SHA256",
                }
            )
            continue
        seen_hashes[digest] = str(path)
        document["selection_reason"] = (
            f"Attachment otomatis dari profile {cv_selection.cv_id}"
        )
        selection.automatic_attachments.append(document)

    required_types = _required_document_types(job, result, rules)
    selection.required_document_types = required_types
    include_supporting = bool(
        settings.get("include_supporting_documents_when_required", True)
    )
    selected_support_types: set[str] = set()

    for path in _folder_files(supporting_folder):
        document_type = _classify_supporting_document(path, rules)
        sensitive = _is_sensitive(path, rules)
        if sensitive:
            selection.rejected_files.append(
                _reject(
                    path,
                    "SUPPORTING_DOCUMENT",
                    "MANUAL_APPROVAL_REQUIRED",
                    document_type=document_type,
                    sensitive=True,
                )
            )
            continue

        document, rejection_reason = _validate_document_file(
            path, settings, "SUPPORTING_DOCUMENT"
        )
        if document is None:
            selection.rejected_files.append(
                _reject(
                    path,
                    "SUPPORTING_DOCUMENT",
                    rejection_reason,
                    document_type=document_type,
                )
            )
            continue
        document["document_type"] = document_type

        if not document_type:
            selection.rejected_files.append(
                {
                    **document,
                    "reason": "UNCLASSIFIED_SUPPORTING_DOCUMENT",
                }
            )
            continue
        if not include_supporting or document_type not in required_types:
            selection.rejected_files.append(
                {
                    **document,
                    "reason": "NOT_REQUIRED_FOR_JOB",
                }
            )
            continue

        digest = str(document["sha256"])
        if digest in seen_hashes:
            selection.duplicate_files.append(
                {
                    **document,
                    "duplicate_of": seen_hashes[digest],
                    "reason": "DUPLICATE_SHA256",
                }
            )
            continue
        seen_hashes[digest] = str(path)
        document["selection_reason"] = (
            f"Lowongan secara eksplisit meminta dokumen tipe {document_type}"
        )
        selection.selected_supporting_documents.append(document)
        selected_support_types.add(document_type)

    missing_types = sorted(set(required_types) - selected_support_types)
    selection.missing_required_document_types = missing_types

    selected_files = selection.selected_files
    selection.total_file_count = len(selected_files)
    selection.total_size_bytes = sum(int(item.get("size", 0)) for item in selected_files)
    selection.selection_reasons = [
        f"Profile dokumen: {cv_selection.cv_id}",
        f"CV: {cv_path.name}",
        f"Attachment otomatis: {len(selection.automatic_attachments)} file",
        f"Supporting document terpilih: {len(selection.selected_supporting_documents)} file",
    ]

    max_total_bytes = max(
        1.0, _float(settings.get("max_total_attachment_mb", 20), 20.0)
    ) * 1024 * 1024
    if missing_types:
        selection.status = "REVIEW_DOCUMENT"
        selection.warnings.append(
            "Dokumen yang diminta lowongan belum tersedia: " + ", ".join(missing_types)
        )
    elif selection.total_size_bytes > max_total_bytes:
        selection.status = "REVIEW_ATTACHMENT_SIZE"
        selection.warnings.append(
            f"Total lampiran {selection.total_size_bytes} byte melebihi batas "
            f"{int(max_total_bytes)} byte"
        )
    else:
        selection.status = "READY"

    sensitive_count = sum(
        1
        for item in selection.rejected_files
        if item.get("reason") == "MANUAL_APPROVAL_REQUIRED"
    )
    if sensitive_count:
        selection.warnings.append(
            f"{sensitive_count} dokumen sensitif ditahan dan tidak dilampirkan otomatis"
        )
    return selection


def audit_document_library(
    profile: dict[str, Any], settings: dict[str, Any]
) -> list[dict[str, Any]]:
    library = load_cv_library(profile, settings)
    rows: list[dict[str, Any]] = []
    for entry in library.get("profiles", []):
        if not isinstance(entry, dict):
            continue
        profile_id = str(entry.get("id", "unnamed")).strip() or "unnamed"
        attachment_folder, supporting_folder = _profile_folders(entry, profile_id)
        attachment_folder = str(resolve_config_path(attachment_folder, settings))
        supporting_folder = str(resolve_config_path(supporting_folder, settings))
        rows.append(
            {
                "profile_id": profile_id,
                "enabled": bool(entry.get("enabled", True)),
                "cv_folder": str(entry.get("cv_folder", "")).strip(),
                "legacy_cv_path": str(entry.get("path", "")).strip(),
                "attachment_folder": attachment_folder,
                "attachment_count": len(_folder_files(attachment_folder)),
                "supporting_document_folder": supporting_folder,
                "supporting_document_count": len(_folder_files(supporting_folder)),
            }
        )
    return rows
