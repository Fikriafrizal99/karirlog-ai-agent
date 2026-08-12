"""CSV writer for discovered jobs — the Search → Execution hand-off artifact.

Writes exactly CSV_COLUMNS (15 fields), UTF-8-SIG, using the shared contract's
serializer so the format can never drift from what the Execution loader expects.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable

from karirlog_contracts.job import CSV_COLUMNS, Job, job_to_csv_row, now_iso

logger = logging.getLogger("karirlog_search.csv_writer")


def write_discovery_csv(
    jobs: Iterable[Job],
    output_dir: str | Path,
    run_id: str,
    timestamp: str,
) -> tuple[Path, Path]:
    """Write jobs to two CSV files and return (timestamped_path, latest_path).

    - data/output/discovery_<timestamp>.csv
    - data/output/discovery_latest.csv

    ``discovered_at`` and ``discovery_run_id`` are stamped onto every row that
    does not already carry them.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamped = out_dir / f"discovery_{timestamp}.csv"
    latest = out_dir / "discovery_latest.csv"

    discovered_at = now_iso()
    rows: list[dict[str, str]] = []
    for job in jobs:
        if not job.discovered_at:
            job.discovered_at = discovered_at
        if not job.discovery_run_id:
            job.discovery_run_id = run_id
        rows.append(job_to_csv_row(job))

    _write_rows(timestamped, rows)
    _write_rows(latest, rows)

    logger.info("CSV ditulis: %s (%d baris)", timestamped.name, len(rows))
    logger.info("CSV terbaru: %s", latest)
    return timestamped, latest


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    # utf-8-sig so Excel on Windows reads the BOM and renders UTF-8 correctly.
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_COLUMNS))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
