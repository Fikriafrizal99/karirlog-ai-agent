from __future__ import annotations

from pathlib import Path


def test_execute_launcher_requires_manual_handoff() -> None:
    project_root = Path(__file__).resolve().parents[1]
    launcher = project_root / "launcher" / "execute_latest.bat"
    text = launcher.read_text(encoding="utf-8").lower()

    assert "data\\input\\discovery_latest.csv" in text
    assert "karirlog-search" not in text
    assert "csv handoff manual" in text
