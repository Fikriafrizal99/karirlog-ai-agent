from __future__ import annotations

from apply_assistant import make_parser, portal_only_destination, trusted_csv_analysis
from karirlog_contracts.job import Job


def _job() -> Job:
    return Job(
        title="Sales Supervisor",
        company="Contoh Finance",
        location="Jakarta",
        url="https://www.kitalulus.com/lowongan/detail/contoh",
        description="Lowongan yang sudah direview manual.",
        source="KitaLulus",
        apply_email="recruitment@example.com",
        fingerprint="abc123",
    )


def test_trusted_csv_analysis_locks_apply_without_ai_or_rule_metadata() -> None:
    result = trusted_csv_analysis(_job(), {}, {})

    assert result.decision == "APPLY"
    assert result.score == 100
    assert result.confidence == 100
    assert result.analysis_mode == "TRUSTED_CSV"
    assert result.provider == "manual_review"
    assert result.model == ""
    assert result.matched_roles == ["Sales Supervisor"]


def test_portal_only_ignores_email_and_uses_original_job_url() -> None:
    job = _job()
    channel, recipient, warnings = portal_only_destination(job)

    assert channel == "PORTAL"
    assert recipient == job.url
    assert any("apply_email diabaikan" in warning for warning in warnings)


def test_parser_exposes_trusted_csv_and_portal_limit_flags() -> None:
    args = make_parser().parse_args(
        [
            "--analysis-mode",
            "trusted_csv",
            "--portal-only",
            "--skip-gmail",
            "--portal-limit",
            "100",
        ]
    )

    assert args.analysis_mode == "trusted_csv"
    assert args.portal_only is True
    assert args.skip_gmail is True
    assert args.portal_limit == 100
