from __future__ import annotations

import json
from pathlib import Path

from apply_assistant import build_active_profile


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_execution_focus_overlay_replaces_legacy_roles_and_preserves_private_fields() -> None:
    focus = _load_json(PROJECT_ROOT / "config" / "execution_focuses.json")
    private_profile = {
        "full_name": "Private Candidate",
        "email": "private@example.test",
        "target_roles": ["Management Trainee", "Account Officer"],
        "transferable_skills": ["Communication"],
        "skill_catalog": ["Sales"],
    }

    active = build_active_profile(private_profile, focus)

    assert active["full_name"] == "Private Candidate"
    assert active["email"] == "private@example.test"
    assert "Management Trainee" not in active["target_roles"]
    assert "Account Officer" not in active["target_roles"]
    assert "Branch Marketing Head" in active["target_roles"]
    assert "Project Coordinator" in active["target_roles"]
    assert "Operations Officer" in active["target_roles"]
    assert "Project Coordination" in active["transferable_skills"]
    assert "Process Improvement" in active["transferable_skills"]
    assert not any("sap" in role.lower() for role in active["target_roles"])


def test_apply_assistant_defaults_to_guarded_one_command_delivery() -> None:
    settings = _load_json(PROJECT_ROOT / "config" / "execution_settings.json")
    assistant = settings["apply_assistant"]

    assert assistant["auto_create_gmail_drafts"] is True
    assert assistant["auto_assist_portal_queue"] is True
    assert settings["gmail"]["send_mode"] == "draft_only"
    assert settings["portal_assistant"]["submit_mode"] == "manual_only"

    launcher = (PROJECT_ROOT / "launcher" / "execute_latest.bat").read_text(
        encoding="utf-8"
    ).lower()
    assert "data\\input\\discovery_latest.csv" in launcher
    assert "apply_assistant.py" in launcher
    assert "karirlog-search" not in launcher
