from __future__ import annotations

import csv
from pathlib import Path

from karirlog_contracts.job import CSV_COLUMNS, Job
from karirlog_search.csv_writer import write_discovery_csv
from karirlog_execution.input_loader import load_jobs_from_csv


def test_search_csv_is_execution_loader_compatible(tmp_path: Path) -> None:
    job = Job(
        title="Sales Supervisor",
        company="Integration Fixture",
        location="Bandung",
        url="https://example.test/integration",
        description="Memimpin tim sales",
        source="integration",
        apply_email="hr@example.test",
        posted_at="2026-08-05",
        source_job_id="integration-1",
        remote=False,
        fingerprint="integration-fingerprint",
    )
    _, latest = write_discovery_csv([job], tmp_path, "integration-run", "20260805_220000")
    with latest.open("r", encoding="utf-8-sig", newline="") as handle:
        assert csv.DictReader(handle).fieldnames == list(CSV_COLUMNS)
    result = load_jobs_from_csv(latest)
    assert result.valid == 1
    assert result.jobs[0].fingerprint == job.fingerprint
