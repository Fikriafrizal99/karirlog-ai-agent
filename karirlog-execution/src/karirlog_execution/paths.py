"""Project-relative path helpers for the Execution Engine."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_path(value: str | Path, root: str | Path = PROJECT_ROOT) -> Path:
    text = os.path.expandvars(os.path.expanduser(str(value)))
    path = Path(text)
    return path if path.is_absolute() else Path(root) / path


def project_root(settings: dict[str, Any] | None = None) -> Path:
    if settings:
        configured = settings.get("_project_root")
        if configured:
            return resolve_path(str(configured), PROJECT_ROOT)
    return PROJECT_ROOT


def resolve_settings(settings: dict[str, Any], root: str | Path = PROJECT_ROOT) -> dict[str, Any]:
    """Resolve every runtime path owned by Execution relative to its project."""
    normalized = dict(settings)
    root_path = Path(root).resolve()
    normalized["_project_root"] = str(root_path)
    for key in (
        "database_path",
        "input_csv",
        "output_dir",
        "cv_library_config",
        "document_rules_config",
        "credentials_path",
        "browser_profile",
    ):
        if normalized.get(key):
            normalized[key] = str(resolve_path(normalized[key], root_path))

    gmail = dict(normalized.get("gmail", {}))
    for key in ("credentials_path", "token_path"):
        if gmail.get(key):
            gmail[key] = str(resolve_path(gmail[key], root_path))
    normalized["gmail"] = gmail

    portal = dict(normalized.get("portal_assistant", {}))
    for key in ("user_data_dir", "artifact_dir", "external_user_data_dir"):
        if portal.get(key):
            portal[key] = str(resolve_path(portal[key], root_path))
    normalized["portal_assistant"] = portal
    return normalized


def resolve_config_path(value: str | Path, settings: dict[str, Any]) -> Path:
    return resolve_path(value, project_root(settings))
