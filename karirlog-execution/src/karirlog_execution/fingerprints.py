"""Stable fingerprints used by the Execution anti-reprocess policy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .paths import resolve_config_path


def _digest(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_signature(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    if path.is_file():
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            return {"path": str(path), "kind": "file", "size": path.stat().st_size, "sha256": digest}
        except OSError:
            return {"path": str(path), "kind": "file", "readable": False}
    files: list[dict[str, Any]] = []
    try:
        for child in sorted(path.rglob("*")):
            if child.is_file() and not child.name.startswith((".", "~$")):
                files.append(_file_signature(child))
    except OSError:
        return {"path": str(path), "kind": "directory", "readable": False}
    return {"path": str(path), "kind": "directory", "files": files}


def _setting_subset(settings: dict[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    return {key: settings.get(key) for key in keys}


def analysis_config_fingerprint(profile: dict[str, Any], settings: dict[str, Any]) -> str:
    """Fingerprint only inputs that can change an analysis decision."""
    return _digest(
        {
            "profile": profile,
            "settings": _setting_subset(
                settings,
                (
                    "analysis_mode",
                    "apply_threshold",
                    "review_threshold",
                    "ai_provider",
                    "ai_model",
                    "openai_responses_url",
                    "max_years_required",
                    "reanalyze_fallback_when_ai_ready",
                ),
            ),
        }
    )


def package_config_fingerprint(profile: dict[str, Any], settings: dict[str, Any]) -> str:
    """Fingerprint package inputs, including CV/document file changes."""
    paths: list[Path] = []
    for key in ("cv_library_config", "document_rules_config"):
        value = settings.get(key)
        if value:
            paths.append(resolve_config_path(str(value), settings))

    cv_library = paths[0] if paths else None
    if cv_library and cv_library.exists():
        try:
            payload = json.loads(cv_library.read_text(encoding="utf-8"))
            for entry in payload.get("profiles", []):
                if not isinstance(entry, dict):
                    continue
                for key in (
                    "path",
                    "cv_folder",
                    "attachment_folder",
                    "supporting_document_folder",
                ):
                    value = str(entry.get(key, "")).strip()
                    if value:
                        paths.append(resolve_config_path(value, settings))
        except (OSError, ValueError, TypeError):
            pass

    return _digest(
        {
            "profile": profile,
            "settings": _setting_subset(
                settings,
                (
                    "output_dir",
                    "copy_selected_cv_to_package",
                    "cv_library_config",
                    "document_rules_config",
                    "allowed_cv_extensions",
                    "allowed_attachment_extensions",
                    "min_cv_size_bytes",
                    "max_cv_size_mb",
                    "cv_min_selection_score",
                    "cv_ambiguity_margin",
                    "include_supporting_documents_when_required",
                    "max_attachment_size_mb",
                    "max_total_attachment_mb",
                ),
            ),
            "files": [_file_signature(path) for path in paths],
        }
    )
