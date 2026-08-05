"""Shared-contract tests (mandatory test #10: shared contract + round-trip)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from karirlog_contracts.job import (  # noqa: E402
    CSV_COLUMNS,
    REQUIRED_FIELDS,
    Job,
    job_from_csv_row,
    job_to_csv_row,
    normalize_posted_at,
    normalize_remote,
    validate_header,
    validate_row,
)


def _sample_job() -> Job:
    return Job(
        title="Sales Manager",
        company="PT Contoh",
        location="Jakarta",
        url="https://example.com/job/1",
        description="Deskripsi lowongan",
        source="brave_search",
        apply_email="hr@example.com",
        posted_at="2026-08-01",
        source_job_id="abc-1",
        employment_type="Full-time",
        salary="10.000.000",
        remote=True,
        fingerprint="fp-123",
        discovered_at="2026-08-05T20:00:00+07:00",
        discovery_run_id="20260805_200000",
    )


def test_csv_columns_are_fifteen():
    assert len(CSV_COLUMNS) == 15
    assert CSV_COLUMNS[0] == "title"
    assert CSV_COLUMNS[-1] == "discovery_run_id"


def test_required_fields():
    assert set(REQUIRED_FIELDS) == {"title", "company", "url", "fingerprint"}


def test_round_trip_preserves_every_field():
    job = _sample_job()
    row = job_to_csv_row(job)
    # Serialized row must have exactly the 15 contract columns.
    assert set(row.keys()) == set(CSV_COLUMNS)
    restored = job_from_csv_row(row)
    for column in CSV_COLUMNS:
        assert getattr(restored, column) == getattr(job, column), column


def test_remote_serializes_as_true_false():
    row = job_to_csv_row(_sample_job())
    assert row["remote"] == "true"
    job2 = _sample_job()
    job2.remote = False
    assert job_to_csv_row(job2)["remote"] == "false"


def test_normalize_remote_variants():
    for truthy in ("true", "1", "yes", "ya", "remote", "WFH", True):
        assert normalize_remote(truthy) is True
    for falsy in ("false", "0", "no", "", None, "onsite"):
        assert normalize_remote(falsy) is False


def test_normalize_posted_at_passthrough():
    assert normalize_posted_at("2026-08-01") == "2026-08-01"
    assert normalize_posted_at("") == ""
    assert normalize_posted_at(None) == ""


def test_validate_row_reports_missing_required():
    row = {"title": "x", "company": "", "url": "u", "fingerprint": ""}
    missing = validate_row(row)
    assert "company" in missing and "fingerprint" in missing
    assert "title" not in missing


def test_validate_header_detects_missing_columns():
    good = list(CSV_COLUMNS)
    assert validate_header(good) == []
    bad = [c for c in CSV_COLUMNS if c != "fingerprint"]
    assert "fingerprint" in validate_header(bad)
