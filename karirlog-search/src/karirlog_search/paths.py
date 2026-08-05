"""Project-relative path helpers for the Search Engine.

The command line entrypoint is intentionally runnable from any working
directory. Relative paths in JSON configuration therefore resolve from the
Search project root, never from ``Path.cwd()``.
"""

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
    """Return settings with every Search-owned default path absolute."""
    normalized = dict(settings)
    root_path = Path(root).resolve()
    normalized["_project_root"] = str(root_path)
    for key in ("sources_config", "input_csv", "output_dir", "diagnostics_dir", "cache_dir"):
        if normalized.get(key):
            normalized[key] = str(resolve_path(normalized[key], root_path))
    return normalized


def resolve_sources_config(
    sources_config: dict[str, Any],
    settings: dict[str, Any],
) -> dict[str, Any]:
    """Normalize path-bearing source settings without changing collector logic."""
    root = project_root(settings)
    normalized = dict(sources_config)
    normalized["_project_root"] = str(root)
    sources: list[dict[str, Any]] = []
    for raw in sources_config.get("sources", []):
        if not isinstance(raw, dict):
            continue
        source = dict(raw)
        for key in ("path", "cache_dir", "diagnostics_path"):
            if source.get(key):
                source[key] = str(resolve_path(source[key], root))
        sources.append(source)
    normalized["sources"] = sources
    return normalized
