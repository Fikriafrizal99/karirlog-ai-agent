from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from ..models import Job
from .base import JobSource
from .fingerprint import make_job_fingerprint
from .http_client import HttpClient
from .parsing import clean_html, parse_jobposting_html


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(element: ET.Element, *names: str) -> str:
    wanted = {name.lower() for name in names}
    for child in list(element):
        if _local_name(child.tag) in wanted:
            return "".join(child.itertext()).strip()
    return ""


def _entry_link(element: ET.Element) -> str:
    for child in list(element):
        if _local_name(child.tag) != "link":
            continue
        href = str(child.attrib.get("href", "")).strip()
        rel = str(child.attrib.get("rel", "alternate")).lower()
        if href and rel in {"alternate", ""}:
            return href
        text = (child.text or "").strip()
        if text:
            return text
    return ""


def _parse_feed(content: bytes) -> tuple[str, list[dict[str, str]]]:
    root = ET.fromstring(content)
    feed_name = _child_text(root, "title")
    if not feed_name:
        for child in list(root):
            if _local_name(child.tag) == "channel":
                feed_name = _child_text(child, "title")
                break
    feed_name = feed_name or "RSS"
    entries: list[dict[str, str]] = []
    for element in root.iter():
        if _local_name(element.tag) not in {"item", "entry"}:
            continue
        author = _child_text(element, "author", "creator")
        if not author:
            for child in list(element):
                if _local_name(child.tag) == "author":
                    author = _child_text(child, "name")
                    break
        entries.append(
            {
                "title": _child_text(element, "title"),
                "link": _entry_link(element),
                "description": _child_text(element, "description", "summary", "content"),
                "published": _child_text(element, "pubdate", "published", "updated"),
                "id": _child_text(element, "guid", "id"),
                "author": author,
            }
        )
    return clean_html(feed_name), entries


class RssJobSource(JobSource):
    def __init__(
        self,
        config: dict[str, Any],
        http: HttpClient,
        max_jobs: int = 100,
    ):
        self.config = config
        self.http = http
        self.max_jobs = max_jobs
        self.feeds = [str(value) for value in config.get("feeds", []) if value]
        self.hydrate_pages = bool(config.get("hydrate_pages", True))
        self.warnings: list[str] = []

    def collect(self) -> list[Job]:
        jobs: list[Job] = []
        for feed_url in self.feeds:
            if len(jobs) >= self.max_jobs:
                break
            try:
                response = self.http.get(feed_url)
                feed_name, entries = _parse_feed(response.content)
            except Exception as exc:
                self.warnings.append(f"{feed_url}: {exc}")
                continue
            for entry in entries:
                if len(jobs) >= self.max_jobs:
                    break
                url = entry["link"]
                if not url:
                    continue

                if self.hydrate_pages:
                    try:
                        page = self.http.get(url)
                        parsed = parse_jobposting_html(page.text, url, f"RSS:{feed_name}")
                    except Exception as exc:
                        self.warnings.append(f"Gagal membaca {url}: {exc}")
                        parsed = []
                    if parsed:
                        jobs.extend(parsed[: self.max_jobs - len(jobs)])
                        continue

                title = clean_html(entry["title"])
                description = clean_html(entry["description"])
                company = clean_html(entry["author"]) or feed_name
                if not title or not description:
                    continue
                job = Job(
                    title=title,
                    company=company,
                    location="",
                    url=url,
                    description=description,
                    source=f"RSS:{feed_name}",
                    posted_at=entry["published"],
                    source_job_id=entry["id"],
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
