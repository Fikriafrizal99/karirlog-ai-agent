"""KarirLog shared contracts — Job model and CSV interchange format."""

from __future__ import annotations

from .job import (
    CONTRACT_VERSION,
    CSV_COLUMNS,
    CSV_CONTRACT_VERSION,
    REQUIRED_FIELDS,
    Job,
    job_from_csv_row,
    job_to_csv_row,
    normalize_posted_at,
    normalize_remote,
    now_iso,
    validate_header,
    validate_contract_header,
    validate_row,
)

__all__ = [
    "CONTRACT_VERSION",
    "CSV_COLUMNS",
    "CSV_CONTRACT_VERSION",
    "REQUIRED_FIELDS",
    "Job",
    "job_from_csv_row",
    "job_to_csv_row",
    "normalize_posted_at",
    "normalize_remote",
    "now_iso",
    "validate_header",
    "validate_contract_header",
    "validate_row",
]

__version__ = "1.0.0"
