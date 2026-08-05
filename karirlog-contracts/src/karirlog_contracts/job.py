"""KarirLog shared contract: the Job model and the CSV interchange format.

This package is the single source of truth for the data that flows from the
Search Engine to the Execution Engine. Both engines import ``Job`` and the CSV
helpers from here so the CSV contract can never silently diverge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping


# CSV remains a deliberately flat, 15-column interchange format. Versioning
# is metadata for loaders and diagnostics; it is not an extra CSV column so
# existing handoff files remain compatible.
CONTRACT_VERSION = "1.0"
CSV_CONTRACT_VERSION = CONTRACT_VERSION


# The exact column order written by the Search Engine and read by the
# Execution Engine. Keep this in sync with Job's serialisable fields.
CSV_COLUMNS: tuple[str, ...] = (
    "title",
    "company",
    "location",
    "url",
    "description",
    "source",
    "apply_email",
    "posted_at",
    "source_job_id",
    "employment_type",
    "salary",
    "remote",
    "fingerprint",
    "discovered_at",
    "discovery_run_id",
)

# A row is rejected by the Execution loader if any of these are blank.
REQUIRED_FIELDS: tuple[str, ...] = ("title", "company", "url", "fingerprint")

_TRUTHY = {"1", "true", "yes", "ya", "y", "remote", "wfh"}


@dataclass(slots=True)
class Job:
    """A single job vacancy. Mirrors the legacy karirlog.models.Job plus the
    two provenance fields carried by the CSV contract."""

    title: str
    company: str
    location: str
    url: str
    description: str
    source: str = "unknown"
    apply_email: str = ""
    posted_at: str = ""
    source_job_id: str = ""
    employment_type: str = ""
    salary: str = ""
    remote: bool = False
    fingerprint: str = ""
    discovered_at: str = ""
    discovery_run_id: str = ""
    id: int | None = None


def normalize_remote(value: Any) -> bool:
    """Coerce a CSV/raw value into a bool. Truthy: 1/true/yes/ya/y/remote/wfh."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in _TRUTHY


def normalize_posted_at(value: Any) -> str:
    """Trim and safely stringify a posted-at value."""
    if value is None:
        return ""
    return str(value).strip()


def now_iso() -> str:
    """ISO-8601 local timestamp used for discovered_at."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def job_to_csv_row(job: Job) -> dict[str, str]:
    """Serialise a Job into a str->str mapping keyed by CSV_COLUMNS."""
    return {
        "title": job.title or "",
        "company": job.company or "",
        "location": job.location or "",
        "url": job.url or "",
        "description": job.description or "",
        "source": job.source or "",
        "apply_email": job.apply_email or "",
        "posted_at": job.posted_at or "",
        "source_job_id": job.source_job_id or "",
        "employment_type": job.employment_type or "",
        "salary": job.salary or "",
        "remote": "true" if job.remote else "false",
        "fingerprint": job.fingerprint or "",
        "discovered_at": job.discovered_at or "",
        "discovery_run_id": job.discovery_run_id or "",
    }


def job_from_csv_row(row: Mapping[str, Any]) -> Job:
    """Deserialise a CSV row (dict) into a Job."""
    return Job(
        title=str(row.get("title", "") or "").strip(),
        company=str(row.get("company", "") or "").strip(),
        location=str(row.get("location", "") or "").strip(),
        url=str(row.get("url", "") or "").strip(),
        description=str(row.get("description", "") or ""),
        source=str(row.get("source", "") or "").strip() or "unknown",
        apply_email=str(row.get("apply_email", "") or "").strip(),
        posted_at=normalize_posted_at(row.get("posted_at", "")),
        source_job_id=str(row.get("source_job_id", "") or "").strip(),
        employment_type=str(row.get("employment_type", "") or "").strip(),
        salary=str(row.get("salary", "") or "").strip(),
        remote=normalize_remote(row.get("remote", "")),
        fingerprint=str(row.get("fingerprint", "") or "").strip(),
        discovered_at=str(row.get("discovered_at", "") or "").strip(),
        discovery_run_id=str(row.get("discovery_run_id", "") or "").strip(),
    )


def validate_row(row: Mapping[str, Any]) -> list[str]:
    """Return the list of REQUIRED_FIELDS that are missing/blank in ``row``."""
    missing: list[str] = []
    for name in REQUIRED_FIELDS:
        value = row.get(name)
        if value is None or not str(value).strip():
            missing.append(name)
    return missing


def validate_header(fieldnames: Iterable[str] | None) -> list[str]:
    """Return the REQUIRED_FIELDS absent from a CSV header (empty == ok)."""
    present = {str(name).strip() for name in (fieldnames or [])}
    return [name for name in REQUIRED_FIELDS if name not in present]


def validate_contract_header(fieldnames: Iterable[str] | None) -> list[str]:
    """Validate a complete handoff header against the current CSV contract.

    The legacy Search sample input intentionally uses a smaller source format,
    so it is parsed only by the Search CSV collector. The Search-to-Execution
    handoff must contain all 15 columns to make version incompatibilities
    explicit instead of silently turning missing provenance into empty values.
    """
    if fieldnames is None:
        return []
    normalized = [str(name).strip() for name in fieldnames]
    errors: list[str] = []
    duplicates = sorted(
        {name for name in normalized if name and normalized.count(name) > 1}
    )
    if duplicates:
        errors.append("kolom duplikat: " + ", ".join(duplicates))
    missing = [name for name in CSV_COLUMNS if name not in normalized]
    if missing:
        errors.append("kolom kontrak hilang: " + ", ".join(missing))
    return errors
