from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ..models import Job
from .base import JobSource
from .http_client import HttpClient
from .parsing import parse_generic_job_page, parse_jobposting_html


class UrlListJobSource(JobSource):
    def __init__(
        self,
        config: dict[str, Any],
        http: HttpClient,
        max_jobs: int = 100,
    ):
        self.config = config
        self.http = http
        self.max_jobs = max_jobs
        self.path = Path(str(config.get("path", "data/input/job_urls.txt")))
        self.strict_jobposting = bool(config.get("strict_jobposting", False))
        self.warnings: list[str] = []

    def collect(self) -> list[Job]:
        if not self.path.exists():
            return []
        urls = [
            line.strip()
            for line in self.path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

        jobs: list[Job] = []
        for url in urls:
            if len(jobs) >= self.max_jobs:
                break
            try:
                response = self.http.get(url)
            except Exception as exc:
                self.warnings.append(f"{url}: {exc}")
                continue
            source_name = f"URL:{urlsplit(url).netloc.removeprefix('www.')}"
            parsed = parse_jobposting_html(response.text, url, source_name)
            if parsed:
                jobs.extend(parsed[: self.max_jobs - len(jobs)])
                continue
            if not self.strict_jobposting:
                fallback = parse_generic_job_page(response.text, url, source_name)
                if fallback:
                    jobs.append(fallback)
        return jobs
