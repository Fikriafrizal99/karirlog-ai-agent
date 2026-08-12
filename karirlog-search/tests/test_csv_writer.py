"""Search Engine tests: CSV writer (#1) and writer→loader round-trip (#2)."""

import csv
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT.parent / "karirlog-contracts" / "src"))

from karirlog_contracts.job import CSV_COLUMNS, Job, job_from_csv_row  # noqa: E402
from karirlog_search.csv_writer import write_discovery_csv  # noqa: E402


def _jobs():
    return [
        Job(
            title="Sales Supervisor",
            company="PT Satu",
            location="Bandung",
            url="https://example.com/1",
            description="desc 1",
            source="brave_search",
            apply_email="a@example.com",
            posted_at="2026-08-01",
            source_job_id="s1",
            employment_type="Full-time",
            salary="8jt",
            remote=False,
            fingerprint="fp1",
        ),
        Job(
            title="Account Officer",
            company="PT Dua",
            location="Remote",
            url="https://example.com/2",
            description="desc 2 — dengan koma, dan \"tanda kutip\"",
            source="rss",
            apply_email="",
            posted_at="",
            source_job_id="s2",
            employment_type="",
            salary="",
            remote=True,
            fingerprint="fp2",
        ),
    ]


def test_writer_produces_both_files_with_15_columns(tmp_path):
    ts, latest = write_discovery_csv(_jobs(), tmp_path, run_id="20260805_120000", timestamp="20260805_120000")
    assert ts.exists() and latest.exists()
    assert latest.name == "discovery_latest.csv"
    assert ts.name == "discovery_20260805_120000.csv"

    with latest.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == list(CSV_COLUMNS)
        rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["remote"] == "false"
    assert rows[1]["remote"] == "true"
    # provenance stamped
    assert rows[0]["discovery_run_id"] == "20260805_120000"
    assert rows[0]["discovered_at"]


def test_writer_uses_utf8_sig_bom(tmp_path):
    _, latest = write_discovery_csv(_jobs(), tmp_path, run_id="r", timestamp="20260805_120001")
    raw = latest.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "CSV harus diawali BOM UTF-8-SIG"


def test_round_trip_writer_then_contract_parser(tmp_path):
    _, latest = write_discovery_csv(_jobs(), tmp_path, run_id="rid", timestamp="20260805_120002")
    with latest.open("r", encoding="utf-8-sig", newline="") as handle:
        result = list(csv.DictReader(handle))
    assert len(result) == 2

    original = {j.fingerprint: j for j in _jobs()}
    for row in result:
        job = job_from_csv_row(row)
        src = original[job.fingerprint]
        assert job.title == src.title
        assert job.company == src.company
        assert job.url == src.url
        assert job.remote == src.remote
        assert job.source == src.source
