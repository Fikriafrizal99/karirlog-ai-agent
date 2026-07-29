from __future__ import annotations

import csv
from pathlib import Path

from ..models import Job
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
                title = row.get("title", "").strip()
                company = row.get("company", "").strip()
                if not title or not company:
                    continue
                source_job_id = row.get("source_job_id", "").strip()
                job = Job(
                    title=title,
                    company=company,
                    location=row.get("location", "").strip(),
                    url=row.get("url", "").strip(),
                    description=row.get("description", "").strip(),
                    source=row.get("source", "CSV").strip() or "CSV",
                    apply_email=row.get("apply_email", "").strip(),
                    posted_at=row.get("posted_at", "").strip(),
                    source_job_id=source_job_id,
                    employment_type=row.get("employment_type", "").strip(),
                    salary=row.get("salary", "").strip(),
                    remote=row.get("remote", "").strip().lower() in {"1", "true", "yes", "ya"},
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
