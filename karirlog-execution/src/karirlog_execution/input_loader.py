"""CSV input loader for the Execution Engine.

Reads the discovery CSV produced by the Search Engine, validates it against the
shared contract, and returns Job objects. Never imports the discovery package.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

from karirlog_contracts.job import (
    CONTRACT_VERSION,
    CSV_COLUMNS,
    Job,
    job_from_csv_row,
    validate_contract_header,
    validate_header,
    validate_row,
)

logger = logging.getLogger("karirlog_execution.input_loader")


class InputLoaderError(Exception):
    """Raised when the CSV is missing or structurally invalid (bad header)."""


@dataclass(slots=True)
class LoadResult:
    total_rows: int = 0
    jobs: list[Job] = field(default_factory=list)
    valid: int = 0
    failed: int = 0
    duplicates: int = 0
    errors: list[str] = field(default_factory=list)
    contract_version: str = CONTRACT_VERSION


def load_jobs_from_csv(path: str | Path) -> LoadResult:
    """Load and validate jobs from a discovery CSV.

    - Missing file / unreadable → raises InputLoaderError with a clear message.
    - Missing required header columns → raises InputLoaderError.
    - Empty CSV (header only, or completely empty) → LoadResult with 0 jobs, no crash.
    - Rows missing title/company/url/fingerprint are rejected and counted.
    - ``remote`` and ``posted_at`` are normalised via the shared contract.
    """
    csv_path = Path(path)
    if not csv_path.exists():
        raise InputLoaderError(f"File CSV input tidak ditemukan: {csv_path}")
    if not csv_path.is_file():
        raise InputLoaderError(f"Path CSV input bukan file: {csv_path}")

    result = LoadResult()
    try:
        # utf-8-sig strips the BOM that Excel/the Search Engine writes.
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)

            if reader.fieldnames is None:
                logger.warning("CSV kosong (tanpa header): %s", csv_path)
                return result

            header_errors = validate_contract_header(reader.fieldnames)
            if header_errors:
                raise InputLoaderError(
                    "Header CSV tidak valid untuk kontrak "
                    f"{CONTRACT_VERSION}. "
                    + "; ".join(header_errors)
                    + f". Ditemukan: {reader.fieldnames}"
                )

            seen_fingerprints: set[str] = set()
            for line_no, row in enumerate(reader, start=2):
                result.total_rows += 1
                missing = validate_row(row)
                if missing:
                    result.failed += 1
                    message = (
                        f"Baris {line_no} ditolak — field wajib kosong: "
                        + ", ".join(missing)
                    )
                    result.errors.append(message)
                    logger.warning(message)
                    continue
                job = job_from_csv_row(row)
                if job.fingerprint in seen_fingerprints:
                    result.duplicates += 1
                    message = (
                        f"Baris {line_no} dilewati — fingerprint duplikat dalam CSV: "
                        f"{job.fingerprint}"
                    )
                    result.errors.append(message)
                    logger.warning(message)
                    continue
                seen_fingerprints.add(job.fingerprint)
                result.jobs.append(job)
                result.valid += 1
    except InputLoaderError:
        raise
    except (OSError, csv.Error, UnicodeError) as exc:
        raise InputLoaderError(f"Gagal membaca CSV {csv_path}: {exc}") from exc

    logger.info(
        "Input CSV dimuat: %s | total=%d valid=%d gagal=%d duplikat=%d",
        csv_path,
        result.total_rows,
        result.valid,
        result.failed,
        result.duplicates,
    )
    return result
