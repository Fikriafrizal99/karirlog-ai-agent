from __future__ import annotations

import csv
from pathlib import Path

from karirlog_contracts.job import Job, normalize_posted_at, normalize_remote
from .base import JobSource
from .fingerprint import make_job_fingerprint


class CsvJobSource(JobSource):
    REQUIRED_COLUMNS = {"title", "company", "location", "url", "description"}

    def __init__(self, path: str | Path, max_jobs: int = 100):
        self.path = Path(path)
        self.max_jobs = max_jobs

    def collect(self) -> list[Job]:
        if not self.path.exists():
            raise FileNotFoundError(f"CSV lowongan tidak ditemukan: {self.path}")

        jobs: list[Job] = []
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = set(reader.fieldnames or [])
            missing = self.REQUIRED_COLUMNS - columns
            if missing:
                raise ValueError(f"Kolom CSV belum lengkap: {', '.join(sorted(missing))}")

            for row in reader:
                if len(jobs) >= self.max_jobs:
                    break
                title = str(row.get("title", "") or "").strip()
                company = str(row.get("company", "") or "").strip()
                if not title or not company:
                    continue
                source_job_id = str(row.get("source_job_id", "") or "").strip()
                job = Job(
                    title=title,
                    company=company,
                    location=str(row.get("location", "") or "").strip(),
                    url=str(row.get("url", "") or "").strip(),
                    description=str(row.get("description", "") or "").strip(),
                    source=str(row.get("source", "CSV") or "CSV").strip() or "CSV",
                    apply_email=str(row.get("apply_email", "") or "").strip(),
                    posted_at=normalize_posted_at(row.get("posted_at", "")),
                    source_job_id=source_job_id,
                    employment_type=str(row.get("employment_type", "") or "").strip(),
                    salary=str(row.get("salary", "") or "").strip(),
                    remote=normalize_remote(row.get("remote", "")),
                )
                job.fingerprint = make_job_fingerprint(
                    job.title,
                    job.company,
                    job.location,
                    job.url,
                    job.source_job_id,
                )
                jobs.append(job)
        return jobs
