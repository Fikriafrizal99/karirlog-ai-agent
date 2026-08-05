"""Search Engine orchestration: collect jobs → write CSV + diagnostics.

This module deliberately imports NOTHING from analysis, AI, CV, database, or
delivery. Its only job is discovery + CSV export.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .csv_writer import write_discovery_csv
from .discovery import DiscoveryManager

logger = logging.getLogger("karirlog_search.app")


def run_collect(
    profile: dict[str, Any],
    settings: dict[str, Any],
    sources_config: dict[str, Any],
) -> dict[str, Any]:
    """Run discovery and export the result to CSV. Returns a stats dict."""
    now = datetime.now().astimezone()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    run_id = timestamp

    logger.info("Mulai discovery | mode=%s", settings.get("discovery_mode"))
    result = DiscoveryManager(profile, settings, sources_config).collect()

    output_dir = settings.get("output_dir", "data/output")
    timestamped, latest = write_discovery_csv(result.jobs, output_dir, run_id, timestamp)

    logger.info(
        "Selesai | raw=%d unik=%d duplikat_lintas=%d fallback=%s",
        result.raw_found,
        len(result.jobs),
        result.cross_source_duplicates,
        result.fallback_used,
    )
    for report in result.reports:
        logger.info(
            "Collector %-8s | %3d | %s | %s",
            report.status,
            report.found,
            report.name,
            report.message,
        )

    diagnostics_path = Path(output_dir) / "latest_discovery_diagnostics.json"

    return {
        "run_id": run_id,
        "timestamp": timestamp,
        "raw_found": result.raw_found,
        "unique_jobs": len(result.jobs),
        "cross_source_duplicates": result.cross_source_duplicates,
        "fallback_used": result.fallback_used,
        "csv_timestamped": str(timestamped),
        "csv_latest": str(latest),
        "diagnostics_path": str(diagnostics_path) if diagnostics_path.exists() else "",
        "collectors": [report.to_dict() for report in result.reports],
    }
