from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest

from karirlog_contracts.job import CSV_COLUMNS, Job, job_to_csv_row
from karirlog_execution.ai_provider import AIAnalysisError
from karirlog_execution.analysis import analyze_job, analyze_job_rules
from karirlog_execution.application_builder import build_application
from karirlog_execution.config import load_settings
from karirlog_execution.database import Database
from karirlog_execution.document_library import select_documents
from karirlog_execution.cv_selector import select_cv
from karirlog_execution.input_loader import InputLoaderError, load_jobs_from_csv
from karirlog_execution.lifecycle import (
    APPLIED,
    FAILED,
    REVIEW_PENDING,
    SKIPPED,
    lifecycle_for_decision,
    lifecycle_for_status,
)
from karirlog_execution.models import AnalysisResult
from karirlog_execution.paths import resolve_settings
from karirlog_execution.pipeline import run_pipeline


FIXTURE_CV = Path(__file__).parent / "fixtures" / "cv_fixture.pdf"


def make_job(**overrides: object) -> Job:
    values: dict[str, object] = {
        "title": "Sales Supervisor",
        "company": "Fixture Finance",
        "location": "Bandung",
        "url": "https://example.test/jobs/sales-supervisor",
        "description": (
            "Memimpin tim sales, mencapai target, mengelola pipeline, "
            "dan memiliki pengalaman minimal 2 tahun."
        ),
        "source": "fixture",
        "apply_email": "hr@example.test",
        "posted_at": "2026-08-01",
        "source_job_id": "fixture-1",
        "employment_type": "Full-time",
        "salary": "",
        "remote": False,
        "fingerprint": "fixture-fingerprint",
        "discovered_at": "2026-08-05T20:00:00+07:00",
        "discovery_run_id": "fixture-run",
    }
    values.update(overrides)
    return Job(**values)  # type: ignore[arg-type]


def write_contract_csv(path: Path, jobs: list[Job], rows: list[dict[str, str]] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_COLUMNS))
        writer.writeheader()
        for row in rows or [job_to_csv_row(job) for job in jobs]:
            writer.writerow(row)


def fixture_profile() -> dict[str, object]:
    return {
        "full_name": "Fixture Candidate",
        "career_level": "OFFICER_TO_SUPERVISOR",
        "years_experience_target_domain": 3,
        "max_years_required": 5,
        "target_roles": ["Sales Supervisor", "Business Development"],
        "preferred_locations": ["Bandung", "Jawa Barat", "Indonesia"],
        "skills": ["Sales", "Sales Management", "Leadership", "Pipeline Management"],
        "transferable_skills": ["Leadership", "Communication"],
        "experience_summary": "Pengalaman memimpin tim sales dan mengelola target.",
        "excluded_role_keywords": [],
    }


def fixture_settings(tmp_path: Path, cv_path: Path | None = None) -> dict[str, object]:
    root = tmp_path / "execution-project"
    root.mkdir(parents=True, exist_ok=True)
    library_path = root / "config" / "cv_library.json"
    library_path.parent.mkdir(parents=True, exist_ok=True)
    library_path.write_text(
        json.dumps(
            {
                "version": 1,
                "profiles": [
                    {
                        "id": "fixture_sales",
                        "label": "Fixture Sales CV",
                        "path": str(cv_path or root / "missing.pdf"),
                        "enabled": True,
                        "priority": 100,
                        "role_keywords": ["Sales Supervisor"],
                        "skill_keywords": ["Sales", "Leadership"],
                        "excluded_keywords": [],
                        "fallback": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    settings: dict[str, object] = {
        "_project_root": str(root),
        "database_path": str(root / "data" / "database" / "karirlog.db"),
        "input_csv": str(root / "data" / "input" / "discovery_latest.csv"),
        "output_dir": str(root / "data" / "output"),
        "analysis_mode": "rule_only",
        "apply_threshold": 65,
        "review_threshold": 45,
        "build_application_for": ["APPLY"],
        "auto_apply_mode": "draft_only",
        "telegram_enabled": False,
        "cv_library_config": str(library_path),
        "document_rules_config": str(root / "config" / "document_library.json"),
        "allowed_cv_extensions": [".pdf"],
        "min_cv_size_bytes": 100,
        "max_cv_size_mb": 10,
        "cv_min_selection_score": 30,
        "cv_ambiguity_margin": 5,
        "copy_selected_cv_to_package": True,
        "rebuild_incomplete_applications": True,
        "reanalyze_fallback_when_ai_ready": False,
    }
    return resolve_settings(settings, root)


def test_csv_valid(tmp_path: Path) -> None:
    path = tmp_path / "valid.csv"
    write_contract_csv(path, [make_job()])
    result = load_jobs_from_csv(path)
    assert result.total_rows == 1
    assert result.valid == 1
    assert result.failed == 0
    assert result.duplicates == 0
    assert result.jobs[0].fingerprint == "fixture-fingerprint"


def test_csv_empty(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    result = load_jobs_from_csv(path)
    assert result.total_rows == 0
    assert result.jobs == []


def test_csv_without_header_is_rejected_clearly(tmp_path: Path) -> None:
    path = tmp_path / "without-header.csv"
    path.write_text("Sales Supervisor,Fixture Finance,Bandung,https://example.test,desc\n", encoding="utf-8")
    with pytest.raises(InputLoaderError, match="Header CSV tidak valid"):
        load_jobs_from_csv(path)


def test_csv_with_broken_header_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "broken-header.csv"
    path.write_text("title,company,url\nSales,Fixture,https://example.test\n", encoding="utf-8")
    with pytest.raises(InputLoaderError, match="kontrak"):
        load_jobs_from_csv(path)


@pytest.mark.parametrize("field", ["title", "company", "url", "fingerprint"])
def test_rows_missing_required_fields_are_failed(tmp_path: Path, field: str) -> None:
    job = make_job()
    row = job_to_csv_row(job)
    row[field] = ""
    path = tmp_path / f"missing-{field}.csv"
    write_contract_csv(path, [], [row])
    result = load_jobs_from_csv(path)
    assert result.total_rows == 1
    assert result.valid == 0
    assert result.failed == 1
    assert field in result.errors[0]


def test_normalization_remote_and_posted_at(tmp_path: Path) -> None:
    row = job_to_csv_row(make_job(remote=True, posted_at=" 2026-08-02 "))
    path = tmp_path / "normalized.csv"
    write_contract_csv(path, [], [row])
    job = load_jobs_from_csv(path).jobs[0]
    assert job.remote is True
    assert job.posted_at == "2026-08-02"


def test_duplicate_fingerprint_inside_one_csv_is_dropped(tmp_path: Path) -> None:
    first = job_to_csv_row(make_job())
    second = job_to_csv_row(make_job(title="Another title"))
    second["fingerprint"] = first["fingerprint"]
    path = tmp_path / "duplicates.csv"
    write_contract_csv(path, [], [first, second])
    result = load_jobs_from_csv(path)
    assert result.total_rows == 2
    assert result.valid == 1
    assert result.duplicates == 1
    assert len(result.jobs) == 1


def test_database_fresh_is_created_automatically(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "karirlog.db"
    database = Database(path)
    try:
        assert path.exists()
        assert database.connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    finally:
        database.close()


def test_new_job_is_saved_and_fingerprint_is_unique(tmp_path: Path) -> None:
    database = Database(tmp_path / "karirlog.db")
    try:
        job = make_job()
        first_id, first_created = database.insert_job(job)
        second_id, second_created = database.insert_job(job)
        assert first_created is True
        assert second_created is False
        assert first_id == second_id
        assert database.connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
    finally:
        database.close()


def test_rule_only_analysis() -> None:
    result = analyze_job_rules(make_job(), fixture_profile(), {"analysis_mode": "rule_only"})
    assert result.analysis_mode == "RULE_ONLY"
    assert result.decision in {"APPLY", "REVIEW", "SKIP"}
    assert result.score > 0


def test_ai_fallback_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = analyze_job(make_job(), fixture_profile(), {"analysis_mode": "ai_with_fallback"})
    assert result.analysis_mode == "RULE_FALLBACK"
    assert "Fallback lokal" in " ".join(result.reasons)


def test_ai_required_without_api_key_is_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(AIAnalysisError, match="API key belum tersedia"):
        analyze_job(make_job(), fixture_profile(), {"analysis_mode": "ai_required"})


def test_cv_selector_with_fixture(tmp_path: Path) -> None:
    settings = fixture_settings(tmp_path, FIXTURE_CV)
    selection = select_cv(make_job(), analyze_job_rules(make_job(), fixture_profile(), settings), fixture_profile(), settings)
    assert selection.ready
    assert selection.cv_id == "fixture_sales"
    assert selection.sha256


def test_document_selector(tmp_path: Path) -> None:
    settings = fixture_settings(tmp_path, FIXTURE_CV)
    result = analyze_job_rules(make_job(), fixture_profile(), settings)
    cv = select_cv(make_job(), result, fixture_profile(), settings)
    selection = select_documents(make_job(), result, cv, fixture_profile(), settings)
    assert selection.ready
    assert selection.selected_cv["name"] == FIXTURE_CV.name


def test_application_builder_with_cv_fixture(tmp_path: Path) -> None:
    settings = fixture_settings(tmp_path, FIXTURE_CV)
    job = make_job()
    analysis = analyze_job_rules(job, fixture_profile(), settings)
    package = build_application(settings["output_dir"], 1, job, analysis, fixture_profile(), settings)  # type: ignore[arg-type]
    assert package.ready
    package_root = Path(package.output_path)
    for name in (
        "cover_letter.txt",
        "email_subject.txt",
        "email_body.txt",
        "analysis.json",
        "cv_selection.json",
        "document_selection.json",
        "application.json",
        "package_manifest.json",
    ):
        assert (package_root / name).exists(), name
    assert list((package_root / "attachments").glob("*.pdf"))


def test_application_builder_without_cv(tmp_path: Path) -> None:
    settings = fixture_settings(tmp_path, None)
    job = make_job()
    package = build_application(
        settings["output_dir"],
        1,
        job,
        analyze_job_rules(job, fixture_profile(), settings),
        fixture_profile(),
        settings,
    )  # type: ignore[arg-type]
    assert package.status == "BLOCKED_CV_MISSING"
    assert not package.ready


def test_end_to_end_csv_rule_apply_package_and_database(tmp_path: Path) -> None:
    settings = fixture_settings(tmp_path, FIXTURE_CV)
    csv_path = Path(settings["input_csv"])  # type: ignore[arg-type]
    write_contract_csv(csv_path, [make_job()])
    loaded = load_jobs_from_csv(csv_path)
    stats = run_pipeline(loaded.jobs, fixture_profile(), settings)
    assert stats["application_ready"] == 1
    assert stats["rule_analyzed"] == 1

    database = Database(settings["database_path"])  # type: ignore[arg-type]
    try:
        row = database.connection.execute(
            """
            SELECT ap.status, ap.lifecycle_state, ap.output_path, j.lifecycle_state
            FROM applications ap JOIN jobs j ON j.id = ap.job_id
            ORDER BY ap.id DESC LIMIT 1
            """
        ).fetchone()
        assert row["status"] == "DRAFT_READY_EMAIL"
        assert row["lifecycle_state"] == REVIEW_PENDING
        assert row[3] == REVIEW_PENDING
        package_root = Path(row["output_path"])
    finally:
        database.close()
    assert (package_root / "cover_letter.txt").exists()
    assert (package_root / "analysis.json").exists()
    assert (package_root / "package_manifest.json").exists()
    assert list((package_root / "attachments").glob("cv_fixture.pdf"))


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("EMAIL_SENT", APPLIED),
        ("PORTAL_SUBMITTED", APPLIED),
        ("REVIEW", REVIEW_PENDING),
        ("DRAFT_READY_EMAIL", REVIEW_PENDING),
        ("GMAIL_DRAFT_CREATED", REVIEW_PENDING),
        ("EMAIL_APPROVAL_PENDING", REVIEW_PENDING),
        ("BLOCKED_CV_MISSING", FAILED),
        ("SKIP", SKIPPED),
        ("EXPIRED", "EXPIRED"),
    ],
)
def test_lifecycle_mapping(status: str, expected: str) -> None:
    assert lifecycle_for_status(status) == expected


def test_delivery_status_updates_application_and_job_lifecycle(tmp_path: Path) -> None:
    database = Database(tmp_path / "karirlog.db")
    try:
        job_id, _ = database.insert_job(make_job())
        database.save_application(job_id, "DRAFT_READY_EMAIL", "draft_only", "out")
        app = database.connection.execute("SELECT id FROM applications").fetchone()
        database.update_delivery(int(app["id"]), status="EMAIL_SENT", sent=True)
        assert database.get_lifecycle_state(job_id) == APPLIED
        row = database.get_application(int(app["id"]))
        assert row and row["lifecycle_state"] == APPLIED
    finally:
        database.close()


def test_anti_reprocess_and_force_reprocess(tmp_path: Path) -> None:
    settings = fixture_settings(tmp_path, None)
    job = make_job()
    first = run_pipeline([job], fixture_profile(), settings)
    second = run_pipeline([job], fixture_profile(), settings)
    assert first["rule_analyzed"] == 1
    assert second["rule_analyzed"] == 0
    assert second["application_rebuilds"] == 0
    database = Database(settings["database_path"])  # type: ignore[arg-type]
    try:
        before = database.connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
    finally:
        database.close()
    forced = dict(settings)
    forced["force_reprocess"] = True
    third = run_pipeline([job], fixture_profile(), forced)
    assert third["reanalyzed_jobs"] == 1
    database = Database(settings["database_path"])  # type: ignore[arg-type]
    try:
        after = database.connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        assert after == before + 1
    finally:
        database.close()


def test_empty_execution_does_not_crash(tmp_path: Path) -> None:
    settings = fixture_settings(tmp_path, None)
    stats = run_pipeline([], fixture_profile(), settings)
    assert stats["total_found"] == 0
    assert Path(stats["report_path"]).exists()
