from __future__ import annotations

import json
from pathlib import Path


EXEC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXEC_ROOT.parent


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_root_menu_targets_separated_search_and_execution() -> None:
    menu = (REPO_ROOT / "KARIRLOG_MENU.bat").read_text(encoding="utf-8").lower()

    assert "karirlog_search.bat" in menu
    assert "karirlog_execution.bat" in menu
    assert "quick start" in menu
    assert "report" in menu
    assert "telegram" in menu
    assert "set / sync telegram" in menu
    assert "gmail" in menu
    assert "job portal" in menu
    assert "api usage / cost audit" in menu
    assert "setup / install" in menu
    assert "setup search environment" in menu
    assert "setup execution environment" in menu
    assert "set / update openai api key" in menu
    assert "candidate_profile.example.json" in menu
    assert "karirlog-tools\\control.py" in menu


def test_ai_cost_guard_limits_description_and_reasoning() -> None:
    settings = _load_json(EXEC_ROOT / "config" / "execution_settings.json")
    source = (
        EXEC_ROOT / "src" / "karirlog_execution" / "ai_provider.py"
    ).read_text(encoding="utf-8")

    assert settings["ai_model"] == "gpt-5-mini"
    assert settings["ai_max_description_chars"] == 8000
    assert settings["ai_max_output_tokens"] == 1800
    assert settings["ai_reasoning_effort"] == "minimal"
    assert "job.description[: self.max_description_chars]" in source
    assert 'payload["reasoning"] = {"effort": self.reasoning_effort}' in source


def test_control_helper_never_prints_secret_values_by_default() -> None:
    source = (REPO_ROOT / "karirlog-tools" / "control.py").read_text(encoding="utf-8")

    assert "Credential hanya ditampilkan sebagai READY/MISSING" in source
    assert "BRAVE_USD_PER_1000_REQUESTS" in source
    assert "OPENAI_PRICING" in source
    assert "command_telegram_config" in source
    assert "command_openai_config" in source
    assert "getpass.getpass" in source
    assert '"OPENAI_API_KEY": key' in source
