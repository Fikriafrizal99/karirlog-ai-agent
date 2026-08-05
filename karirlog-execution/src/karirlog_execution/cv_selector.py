from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from .config import load_json
from .models import AnalysisResult, CVSelection, Job
from .paths import resolve_config_path

TOKEN_RE = re.compile(r"[a-zA-Z0-9+#./-]+")
DEFAULT_ROLE_KEYWORDS: dict[str, list[str]] = {
    "sap_abap": ["sap abap", "abap developer", "abap programmer", "sap technical"],
    "sap_erp": ["sap", "erp", "sap consultant"],
    "project_management": ["project manager", "project coordinator", "project management", "pmo"],
    "sales_management": ["sales", "business development", "account executive", "marketing"],
    "general": [],
}


def normalize(value: str) -> str:
    return " ".join(TOKEN_RE.findall(str(value).lower()))


def _phrase_matches(phrase: str, text: str) -> bool:
    phrase_text = normalize(phrase)
    haystack = normalize(text)
    if not phrase_text:
        return False
    if phrase_text in haystack:
        return True
    tokens = [token for token in phrase_text.split() if len(token) > 1]
    return bool(tokens) and all(token in haystack.split() for token in tokens)


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_cv_library(profile: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    configured_path = str(settings.get("cv_library_config", "config/cv_library.json")).strip()
    configured_file = resolve_config_path(configured_path, settings) if configured_path else None
    if configured_file and configured_file.exists():
        data = load_json(configured_file)
        if not isinstance(data.get("profiles", []), list):
            raise ValueError("config/cv_library.json harus memiliki array profiles")
        return data

    # Backward compatibility for V0.1-V0.3 profile.json.
    entries: list[dict[str, Any]] = []
    for key, path in dict(profile.get("cv_files", {})).items():
        cv_id = str(key).strip()
        entries.append(
            {
                "id": cv_id,
                "label": cv_id.replace("_", " ").title(),
                "path": str(resolve_config_path(path, settings)),
                "enabled": True,
                "priority": 50 if cv_id != "general" else 1,
                "role_keywords": DEFAULT_ROLE_KEYWORDS.get(cv_id, []),
                "skill_keywords": [],
                "excluded_keywords": [],
                "fallback": cv_id == "general",
            }
        )
    return {"version": 1, "profiles": entries}


# Kept for compatibility with older internal imports.
_load_library = load_cv_library


def get_library_profile(
    profile_id: str, profile: dict[str, Any], settings: dict[str, Any]
) -> dict[str, Any] | None:
    library = load_cv_library(profile, settings)
    for entry in library.get("profiles", []):
        if isinstance(entry, dict) and str(entry.get("id", "")).strip() == profile_id:
            return entry
    return None


def _is_hidden_or_temporary(path: Path) -> bool:
    name = path.name.lower()
    return (
        name.startswith(".")
        or name.startswith("~$")
        or name.endswith(".tmp")
        or name.endswith(".temp")
        or name.endswith("~")
    )


def _allowed_cv_extensions(settings: dict[str, Any]) -> set[str]:
    return {
        str(item).lower()
        for item in settings.get("allowed_cv_extensions", [".pdf"])
        if str(item).strip()
    }


def _discover_cv_path(
    entry: dict[str, Any], settings: dict[str, Any]
) -> tuple[str, list[str], bool, list[str]]:
    """Resolve one CV path from a profile.

    New V1.1 profiles use cv_folder. Legacy profiles may keep path. A folder must
    contain exactly one allowed CV so the system never chooses a CV randomly.
    """

    folder_text = str(entry.get("cv_folder", "")).strip()
    if not folder_text:
        path_text = str(entry.get("path", "")).strip()
        return (
            str(resolve_config_path(path_text, settings)) if path_text else "",
            [],
            False,
            [],
        )

    folder = resolve_config_path(folder_text, settings)
    if not folder.exists():
        return "", [f"Folder CV tidak ditemukan: {folder}"], False, []
    if not folder.is_dir():
        return "", [f"cv_folder bukan folder: {folder}"], False, []

    allowed = _allowed_cv_extensions(settings)
    candidates = sorted(
        (
            path
            for path in folder.iterdir()
            if path.is_file()
            and not _is_hidden_or_temporary(path)
            and path.suffix.lower() in allowed
        ),
        key=lambda path: path.name.lower(),
    )
    candidate_names = [str(path) for path in candidates]
    if not candidates:
        return "", [f"Tidak ada CV valid di folder: {folder}"], False, candidate_names
    if len(candidates) > 1:
        return (
            str(folder),
            [
                f"Ditemukan {len(candidates)} CV di {folder}. "
                "Sisakan tepat satu CV agar pemilihan tidak acak."
            ],
            True,
            candidate_names,
        )
    return str(candidates[0]), [], False, candidate_names


def _validate_file(path_text: str, settings: dict[str, Any]) -> tuple[bool, list[str], int, str]:
    warnings: list[str] = []
    path = Path(path_text)
    allowed = _allowed_cv_extensions(settings)
    if not path_text.strip():
        return False, ["Path CV kosong"], 0, ""
    if not path.exists():
        return False, [f"File CV tidak ditemukan: {path}"], 0, ""
    if not path.is_file():
        return False, [f"Path CV bukan file: {path}"], 0, ""
    if path.suffix.lower() not in allowed:
        return False, [f"Format CV tidak diizinkan: {path.suffix or '(tanpa ekstensi)'}"], 0, ""

    size = path.stat().st_size
    max_size = max(1, _int(settings.get("max_cv_size_mb", 10), 10)) * 1024 * 1024
    min_size = max(1, _int(settings.get("min_cv_size_bytes", 100), 100))
    if size < min_size:
        warnings.append(f"File CV terlalu kecil atau rusak: {size} byte")
    if size > max_size:
        warnings.append(f"File CV melebihi batas: {size} byte")
    if warnings:
        return False, warnings, size, ""

    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        return False, [f"File CV tidak dapat dibaca: {exc}"], size, ""
    return True, [], size, digest


def _score_profile(
    entry: dict[str, Any],
    job: Job,
    result: AnalysisResult,
) -> tuple[int, list[str]]:
    title = job.title
    full_text = f"{job.title} {job.description} {' '.join(result.matched_roles)}"
    matched_skill_text = " ".join(result.matched_skills)
    reasons: list[str] = []
    score = 0

    title_role_hits = [
        item for item in _strings(entry.get("role_keywords", [])) if _phrase_matches(item, title)
    ]
    body_role_hits = [
        item
        for item in _strings(entry.get("role_keywords", []))
        if item not in title_role_hits and _phrase_matches(item, full_text)
    ]
    skill_hits = [
        item
        for item in _strings(entry.get("skill_keywords", []))
        if _phrase_matches(item, matched_skill_text) or _phrase_matches(item, full_text)
    ]
    exclusions = [
        item
        for item in _strings(entry.get("excluded_keywords", []))
        if _phrase_matches(item, title)
    ]

    if title_role_hits:
        points = min(70, 35 + 12 * (len(title_role_hits) - 1))
        score += points
        reasons.append("Role utama cocok: " + ", ".join(title_role_hits[:4]))
    if body_role_hits:
        points = min(24, 8 * len(body_role_hits))
        score += points
        reasons.append("Konteks role cocok: " + ", ".join(body_role_hits[:4]))
    if skill_hits:
        points = min(25, 5 * len(skill_hits))
        score += points
        reasons.append("Skill pendukung cocok: " + ", ".join(skill_hits[:5]))

    priority = max(0, min(100, _int(entry.get("priority", 0), 0)))
    priority_bonus = round(priority / 20)
    if priority_bonus:
        score += priority_bonus
        reasons.append(f"Prioritas library: +{priority_bonus}")

    if bool(entry.get("fallback", False)):
        fallback_score = max(1, _int(entry.get("fallback_score", 15), 15))
        score = max(score, fallback_score)
        reasons.append("CV fallback umum")

    if exclusions:
        score -= 80
        reasons.append("Konflik role: " + ", ".join(exclusions[:4]))

    return max(0, min(100, score)), reasons


def select_cv(
    job: Job,
    result: AnalysisResult,
    profile: dict[str, Any],
    settings: dict[str, Any],
) -> CVSelection:
    library = load_cv_library(profile, settings)
    entries = [item for item in library.get("profiles", []) if isinstance(item, dict)]
    enabled = [item for item in entries if bool(item.get("enabled", True))]
    if not enabled:
        return CVSelection(
            status="BLOCKED_CV_LIBRARY",
            warnings=["Tidak ada profil CV aktif pada library"],
        )

    candidates: list[dict[str, Any]] = []
    valid_candidates: list[dict[str, Any]] = []
    multiple_candidates: list[dict[str, Any]] = []
    invalid_warnings: list[str] = []
    for entry in enabled:
        cv_id = str(entry.get("id", "")).strip() or "unnamed"
        label = str(entry.get("label", cv_id)).strip() or cv_id
        path, discovery_warnings, multiple_cv, discovered_paths = _discover_cv_path(entry, settings)
        if multiple_cv:
            valid, warnings, size, digest = False, discovery_warnings, 0, ""
        else:
            valid, warnings, size, digest = _validate_file(path, settings)
            warnings = discovery_warnings + warnings
        score, reasons = _score_profile(entry, job, result)
        candidate = {
            "cv_id": cv_id,
            "profile_id": cv_id,
            "label": label,
            "path": path,
            "cv_folder": str(entry.get("cv_folder", "")).strip(),
            "attachment_folder": str(entry.get("attachment_folder", "")).strip(),
            "supporting_document_folder": str(
                entry.get("supporting_document_folder", "")
            ).strip(),
            "valid": valid,
            "multiple_cv": multiple_cv,
            "discovered_paths": discovered_paths,
            "score": score,
            "file_size": size,
            "sha256": digest,
            "reasons": reasons,
            "warnings": warnings,
        }
        candidates.append(candidate)
        if valid:
            valid_candidates.append(candidate)
        elif multiple_cv:
            multiple_candidates.append(candidate)
            invalid_warnings.extend(f"{label}: {warning}" for warning in warnings)
        else:
            invalid_warnings.extend(f"{label}: {warning}" for warning in warnings)

    valid_candidates.sort(
        key=lambda item: (int(item["score"]), str(item["cv_id"])), reverse=True
    )
    multiple_candidates.sort(
        key=lambda item: (int(item["score"]), str(item["cv_id"])), reverse=True
    )

    if not valid_candidates:
        if multiple_candidates:
            best_multiple = multiple_candidates[0]
            return CVSelection(
                status="REVIEW_MULTIPLE_CV",
                cv_id=str(best_multiple["cv_id"]),
                label=str(best_multiple["label"]),
                source_path=str(best_multiple["path"]),
                score=int(best_multiple["score"]),
                reasons=list(best_multiple["reasons"]),
                warnings=invalid_warnings,
                candidates=candidates,
            )
        return CVSelection(
            status="BLOCKED_CV_MISSING",
            warnings=invalid_warnings or ["Tidak ada file CV valid"],
            candidates=candidates,
        )

    best = valid_candidates[0]
    # A better-matching profile with multiple CV files must be reviewed instead of
    # silently falling back to a lower-scoring profile.
    if multiple_candidates and int(multiple_candidates[0]["score"]) >= int(best["score"]):
        best_multiple = multiple_candidates[0]
        return CVSelection(
            status="REVIEW_MULTIPLE_CV",
            cv_id=str(best_multiple["cv_id"]),
            label=str(best_multiple["label"]),
            source_path=str(best_multiple["path"]),
            score=int(best_multiple["score"]),
            reasons=list(best_multiple["reasons"]),
            warnings=invalid_warnings,
            candidates=candidates,
        )

    runner_up = valid_candidates[1] if len(valid_candidates) > 1 else None
    min_score = max(0, min(100, _int(settings.get("cv_min_selection_score", 30), 30)))
    ambiguity_margin = max(0, _int(settings.get("cv_ambiguity_margin", 5), 5))
    margin = int(best["score"]) - int(runner_up["score"]) if runner_up else int(best["score"])

    status = "READY"
    warnings: list[str] = []
    if int(best["score"]) < min_score:
        status = "REVIEW_CV"
        warnings.append(f"Skor CV terbaik {best['score']} di bawah minimum {min_score}")
    elif runner_up and margin <= ambiguity_margin:
        status = "REVIEW_CV"
        warnings.append(
            f"Pilihan CV ambigu: selisih {margin} poin dengan {runner_up['label']}"
        )

    confidence = max(0, min(100, int(best["score"]) + min(20, max(0, margin))))
    return CVSelection(
        status=status,
        cv_id=str(best["cv_id"]),
        label=str(best["label"]),
        source_path=str(best["path"]),
        score=int(best["score"]),
        confidence=confidence,
        file_size=int(best["file_size"]),
        sha256=str(best["sha256"]),
        reasons=list(best["reasons"]),
        warnings=warnings + invalid_warnings,
        candidates=candidates,
    )


def audit_cv_library(
    profile: dict[str, Any], settings: dict[str, Any]
) -> list[dict[str, Any]]:
    library = load_cv_library(profile, settings)
    output: list[dict[str, Any]] = []
    for entry in library.get("profiles", []):
        if not isinstance(entry, dict):
            continue
        path, discovery_warnings, multiple_cv, discovered_paths = _discover_cv_path(
            entry, settings
        )
        if multiple_cv:
            valid, warnings, size, digest = False, discovery_warnings, 0, ""
        else:
            valid, warnings, size, digest = _validate_file(path, settings)
            warnings = discovery_warnings + warnings
        output.append(
            {
                "cv_id": str(entry.get("id", "unnamed")),
                "label": str(entry.get("label", entry.get("id", "unnamed"))),
                "enabled": bool(entry.get("enabled", True)),
                "path": path,
                "cv_folder": str(entry.get("cv_folder", "")).strip(),
                "attachment_folder": str(entry.get("attachment_folder", "")).strip(),
                "supporting_document_folder": str(
                    entry.get("supporting_document_folder", "")
                ).strip(),
                "multiple_cv": multiple_cv,
                "discovered_paths": discovered_paths,
                "valid": valid,
                "size": size,
                "sha256": digest,
                "warnings": warnings,
            }
        )
    return output
