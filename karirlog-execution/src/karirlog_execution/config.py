from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File konfigurasi tidak ditemukan: {file_path}")
    with file_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Isi konfigurasi harus berupa object JSON: {file_path}")
    return data


def load_settings(path: str | Path) -> dict[str, Any]:
    """Load execution settings and normalise known dirty values.

    The legacy settings.json historically stored ``analysis_mode`` with a
    trailing space (``"rule_only "``). Strip it so downstream comparisons
    against ``"rule_only"`` behave correctly.
    """
    settings = load_json(path)
    mode = settings.get("analysis_mode")
    if isinstance(mode, str):
        settings["analysis_mode"] = mode.strip()
    return settings

