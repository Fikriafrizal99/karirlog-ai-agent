"""JSON config loader for the Search Engine (copied from legacy karirlog.config)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File konfigurasi tidak ditemukan: {file_path}")
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"File konfigurasi bukan JSON valid: {file_path} ({exc})") from exc
    if not isinstance(data, dict):
        raise ValueError(f"File konfigurasi harus berupa objek JSON: {file_path}")
    return data
