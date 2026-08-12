from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

from karirlog_contracts.job import CSV_COLUMNS
from karirlog_search.discovery.manager import DiscoveryManager


def _legacy_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["title", "company", "location", "url", "description", "source", "apply_email", "posted_at"],
        )
        writer.writeheader()
        writer.writerows(rows)


def _settings(tmp_path: Path, csv_path: Path, mode: str = "sample") -> dict[str, object]:
    return {
        "_project_root": str(tmp_path),
        "discovery_mode": mode,
        "input_csv": str(csv_path),
        "sample_input_csv": str(csv_path),
        "max_jobs_per_run": 20,
    }


def _source_config(*sources: dict[str, object]) -> dict[str, object]:
    return {"http": {}, "sources": list(sources)}


def test_discovery_manager_sample_mode(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    _legacy_csv(
        csv_path,
        [
            {
                "title": "Sales Supervisor",
                "company": "PT Sample",
                "location": "Bandung",
                "url": "https://example.test/1",
                "description": "Memimpin tim sales",
                "source": "sample",
                "apply_email": "hr@example.test",
                "posted_at": "2026-08-01",
            }
        ],
    )
    result = DiscoveryManager(
        {},
        _settings(tmp_path, csv_path),
        _source_config({"type": "csv", "name": "Sample", "enabled": True}),
    ).collect()
    assert len(result.jobs) == 1
    assert result.reports[0].status == "SUCCESS"


def test_live_with_fallback_without_brave_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    csv_path = tmp_path / "fallback.csv"
    _legacy_csv(
        csv_path,
        [{
            "title": "Account Officer",
            "company": "PT Fallback",
            "location": "Jakarta",
            "url": "https://example.test/2",
            "description": "Mengelola relasi nasabah",
            "source": "fallback",
            "apply_email": "",
            "posted_at": "",
        }],
    )
    settings = _settings(tmp_path, csv_path, "live_with_fallback")
    sources = _source_config(
        {
            "type": "brave_search",
            "name": "Brave",
            "enabled": True,
            "api_key_env": "BRAVE_SEARCH_API_KEY",
            "queries": [],
        },
        {"type": "csv", "name": "CSV", "enabled": True, "fallback_only": True},
    )
    result = DiscoveryManager({}, settings, sources).collect()
    assert result.fallback_used is True
    assert len(result.jobs) == 1
    assert result.reports[0].status == "SKIPPED"


def test_deduplicates_across_sources(tmp_path: Path) -> None:
    csv_path = tmp_path / "same.csv"
    _legacy_csv(
        csv_path,
        [{
            "title": "Sales Supervisor",
            "company": "PT Same",
            "location": "Bandung",
            "url": "https://example.test/same",
            "description": "Memimpin tim sales",
            "source": "csv",
            "apply_email": "",
            "posted_at": "",
        }],
    )
    sources = _source_config(
        {"type": "csv", "name": "CSV 1", "enabled": True},
        {"type": "csv", "name": "CSV 2", "enabled": True},
    )
    result = DiscoveryManager({}, _settings(tmp_path, csv_path, "all"), sources).collect()
    assert result.raw_found == 2
    assert result.cross_source_duplicates == 1
    assert len(result.jobs) == 1


def test_empty_discovery(tmp_path: Path) -> None:
    csv_path = tmp_path / "empty.csv"
    _legacy_csv(csv_path, [])
    result = DiscoveryManager(
        {},
        _settings(tmp_path, csv_path),
        _source_config({"type": "csv", "name": "Empty", "enabled": True}),
    ).collect()
    assert result.jobs == []
    assert result.raw_found == 0


def test_search_cli_resolves_paths_from_another_working_directory(tmp_path: Path) -> None:
    project = tmp_path / "search-project"
    (project / "config").mkdir(parents=True)
    (project / "data" / "input").mkdir(parents=True)
    (project / "data" / "output").mkdir(parents=True)
    sample = project / "data" / "input" / "sample.csv"
    _legacy_csv(
        sample,
        [{
            "title": "Sales Coordinator",
            "company": "PT Paths",
            "location": "Bandung",
            "url": "https://example.test/path",
            "description": "Koordinasi sales",
            "source": "sample",
            "apply_email": "",
            "posted_at": "",
        }],
    )
    settings_path = project / "config" / "settings.json"
    settings_path.write_text(
        json.dumps({
            "sources_config": str(project / "config" / "sources.json"),
            "input_csv": str(sample),
            "sample_input_csv": str(sample),
            "output_dir": str(project / "data" / "output"),
            "discovery_mode": "sample",
        }),
        encoding="utf-8",
    )
    (project / "config" / "sources.json").write_text(
        json.dumps({"sources": [{"type": "csv", "name": "CSV", "enabled": True}]}),
        encoding="utf-8",
    )
    profile_path = project / "config" / "profile.json"
    profile_path.write_text("{}", encoding="utf-8")
    other_cwd = tmp_path / "other-cwd"
    other_cwd.mkdir()
    main = Path(__file__).resolve().parents[1] / "main.py"
    completed = subprocess.run(
        [sys.executable, str(main), "collect", "--settings", str(settings_path), "--profile", str(profile_path), "--mode", "sample"],
        cwd=other_cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (project / "data" / "output" / "discovery_latest.csv").exists()


def test_search_runtime_does_not_import_execution() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src"
    text = "\n".join(path.read_text(encoding="utf-8") for path in source_root.rglob("*.py"))
    assert "karirlog_execution" not in text


def test_contract_writer_has_exact_fifteen_columns() -> None:
    assert len(CSV_COLUMNS) == 15
