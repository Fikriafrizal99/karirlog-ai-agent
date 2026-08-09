from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from karirlog_contracts.job import Job
from .results import CollectorReport, DiscoveryResult
from .brave_query_policy import BraveSearchJobSource
from .csv_source import CsvJobSource
from .http_client import HttpClient
from ..paths import project_root, resolve_path, resolve_sources_config
from .rss_source import RssJobSource
from .url_source import UrlListJobSource


class DiscoveryManager:
    LIVE_TYPES = {"brave_search", "rss", "url_list"}

    def __init__(
        self,
        profile: dict[str, Any],
        settings: dict[str, Any],
        sources_config: dict[str, Any],
    ):
        self.profile = profile
        self.settings = settings
        self.sources_config = resolve_sources_config(sources_config, settings)
        self.max_jobs = int(settings.get("max_jobs_per_run", 100))
        self.mode = str(settings.get("discovery_mode", "live_with_fallback")).lower()
        self.root = project_root(settings)
        self.http = HttpClient(sources_config.get("http", {}))

    def _build_source(self, config: dict[str, Any]):
        collector_type = str(config.get("type", "")).lower()
        if collector_type == "brave_search":
            return BraveSearchJobSource(config, self.profile, self.http, self.max_jobs)
        if collector_type == "rss":
            return RssJobSource(config, self.http, self.max_jobs)
        if collector_type == "url_list":
            return UrlListJobSource(config, self.http, self.max_jobs)
        if collector_type == "csv":
            configured_input = (
                self.settings.get("sample_input_csv")
                if self.mode == "sample"
                else self.settings.get("input_csv")
            )
            path = resolve_path(
                configured_input or config.get("path", ""), self.root
            )
            return CsvJobSource(path, self.max_jobs)
        raise ValueError(f"Tipe collector tidak dikenal: {collector_type}")

    def _is_selected(self, config: dict[str, Any], fallback_phase: bool = False) -> bool:
        if not config.get("enabled", False):
            return False
        collector_type = str(config.get("type", "")).lower()
        fallback_only = bool(config.get("fallback_only", False))
        if fallback_phase:
            return collector_type == "csv" and fallback_only
        if self.mode == "sample":
            return collector_type == "csv"
        if self.mode == "all":
            return True
        if fallback_only:
            return False
        if self.mode in {"live", "live_with_fallback"}:
            return collector_type in self.LIVE_TYPES
        raise ValueError(f"discovery_mode tidak valid: {self.mode}")

    @staticmethod
    def _deduplicate(jobs: list[Job]) -> tuple[list[Job], int]:
        unique: list[Job] = []
        fingerprints: set[str] = set()
        duplicate_count = 0
        for job in jobs:
            if not job.fingerprint:
                continue
            if job.fingerprint in fingerprints:
                duplicate_count += 1
                continue
            fingerprints.add(job.fingerprint)
            unique.append(job)
        return unique, duplicate_count

    def _run_configs(
        self,
        configs: list[dict[str, Any]],
        reports: list[CollectorReport],
    ) -> list[Job]:
        jobs: list[Job] = []
        for config in configs:
            name = str(config.get("name") or config.get("type") or "Collector")
            collector_type = str(config.get("type", "")).lower()
            started = time.perf_counter()
            try:
                source = self._build_source(config)
                source_jobs = source.collect()
                duration_ms = round((time.perf_counter() - started) * 1000)
                warnings = list(getattr(source, "warnings", []))
                message = str(getattr(source, "summary_message", "") or "Collector selesai")
                if warnings and "warning" not in message.lower():
                    message += f"; {len(warnings)} warning"
                reports.append(
                    CollectorReport(
                        name=name,
                        collector_type=collector_type,
                        status="SUCCESS",
                        found=len(source_jobs),
                        duration_ms=duration_ms,
                        message=message,
                    )
                )
                jobs.extend(source_jobs)
            except Exception as exc:
                duration_ms = round((time.perf_counter() - started) * 1000)
                status = "SKIPPED" if "belum diisi" in str(exc).lower() else "FAILED"
                reports.append(
                    CollectorReport(
                        name=name,
                        collector_type=collector_type,
                        status=status,
                        duration_ms=duration_ms,
                        message=str(exc),
                    )
                )
        return jobs

    def collect(self) -> DiscoveryResult:
        source_configs = [
            value
            for value in self.sources_config.get("sources", [])
            if isinstance(value, dict)
        ]
        reports: list[CollectorReport] = []
        selected = [config for config in source_configs if self._is_selected(config)]
        raw_jobs = self._run_configs(selected, reports)
        fallback_used = False

        if self.mode == "live_with_fallback" and not raw_jobs:
            fallback_configs = [
                config for config in source_configs if self._is_selected(config, fallback_phase=True)
            ]
            if fallback_configs:
                fallback_used = True
                raw_jobs.extend(self._run_configs(fallback_configs, reports))

        raw_found = len(raw_jobs)
        jobs, duplicates = self._deduplicate(raw_jobs)
        return DiscoveryResult(
            jobs=jobs[: self.max_jobs],
            reports=reports,
            raw_found=raw_found,
            cross_source_duplicates=duplicates,
            fallback_used=fallback_used,
        )


def export_discovery(result: DiscoveryResult, output_path: str | Path) -> Path:
    import json

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "raw_found": result.raw_found,
        "unique_jobs": len(result.jobs),
        "cross_source_duplicates": result.cross_source_duplicates,
        "fallback_used": result.fallback_used,
        "collectors": [report.to_dict() for report in result.reports],
        "jobs": [
            {
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "description": job.description,
                "source": job.source,
                "apply_email": job.apply_email,
                "posted_at": job.posted_at,
                "source_job_id": job.source_job_id,
                "employment_type": job.employment_type,
                "salary": job.salary,
                "remote": job.remote,
                "fingerprint": job.fingerprint,
            }
            for job in result.jobs
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
