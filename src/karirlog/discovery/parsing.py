from __future__ import annotations

import html as html_lib
import json
import re
from typing import Any, Iterable
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from ..models import Job
from .fingerprint import make_job_fingerprint

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "â€”", "â€“", "Ã¢", "�")


def repair_mojibake(value: Any) -> str:
    """Repair common UTF-8 text decoded as Latin-1/Windows-1252.

    The function is conservative: it only tries a repair when typical mojibake
    markers are present, and keeps the candidate only when the marker score
    improves. It can run more than once for double-encoded text.
    """
    current = "" if value is None else str(value)

    def score(text: str) -> int:
        return sum(text.count(marker) for marker in MOJIBAKE_MARKERS) + text.count("�") * 4

    for _ in range(3):
        current_score = score(current)
        if current_score == 0:
            break
        candidates: list[str] = []
        for encoding in ("latin-1", "cp1252"):
            try:
                candidates.append(current.encode(encoding).decode("utf-8"))
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        if not candidates:
            break
        best = min(candidates, key=score)
        if score(best) >= current_score:
            break
        current = best
    return current


def clean_html(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value if item not in (None, ""))
    soup = BeautifulSoup(str(value), "html.parser")
    text = html_lib.unescape(soup.get_text(" ", strip=True))
    return " ".join(repair_mojibake(text).split())


def _iter_jsonld(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        graph = value.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _iter_jsonld(item)
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _iter_jsonld(item)


def _is_job_posting(item: dict[str, Any]) -> bool:
    item_type = item.get("@type")
    if isinstance(item_type, list):
        return any(str(value).lower() == "jobposting" for value in item_type)
    return str(item_type).lower() == "jobposting"


def _company_name(value: Any) -> str:
    if isinstance(value, dict):
        return clean_html(value.get("name", ""))
    return clean_html(value)


def _address_text(address: Any) -> str:
    if isinstance(address, str):
        return clean_html(address)
    if not isinstance(address, dict):
        return ""
    values = [
        address.get("addressLocality"),
        address.get("addressRegion"),
        address.get("addressCountry"),
    ]
    return ", ".join(clean_html(value) for value in values if value)


def _location_text(item: dict[str, Any]) -> tuple[str, bool]:
    remote = str(item.get("jobLocationType", "")).upper() == "TELECOMMUTE"
    locations = item.get("jobLocation", [])
    if isinstance(locations, dict):
        locations = [locations]
    result: list[str] = []
    if isinstance(locations, list):
        for location in locations:
            if isinstance(location, dict):
                text = _address_text(location.get("address", location))
                if text and text not in result:
                    result.append(text)

    requirements = item.get("applicantLocationRequirements")
    if not result and requirements:
        requirement_items = requirements if isinstance(requirements, list) else [requirements]
        for requirement in requirement_items:
            if isinstance(requirement, dict):
                text = clean_html(requirement.get("name", ""))
                if text:
                    result.append(text)

    if remote and not result:
        result.append("Remote")
    elif remote and "Remote" not in result:
        result.insert(0, "Remote")
    return " | ".join(result), remote


def _salary_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float, str)):
        return clean_html(value)
    if not isinstance(value, dict):
        return ""

    currency = clean_html(value.get("currency", ""))
    inner = value.get("value", value)
    if isinstance(inner, dict):
        min_value = inner.get("minValue")
        max_value = inner.get("maxValue")
        exact_value = inner.get("value")
        unit = clean_html(inner.get("unitText", ""))
        if min_value is not None or max_value is not None:
            amount = f"{min_value or '?'} - {max_value or '?'}"
        elif exact_value is not None:
            amount = str(exact_value)
        else:
            amount = ""
        return " ".join(part for part in (currency, amount, unit) if part)
    return currency


def _identifier_text(value: Any) -> str:
    if isinstance(value, dict):
        return clean_html(value.get("value") or value.get("name") or "")
    return clean_html(value)


def _application_email(email: str, context: str) -> bool:
    candidate = email.strip().lower()
    if not candidate:
        return False
    local = candidate.split("@", 1)[0]
    nearby = clean_html(context).lower()
    apply_signal = bool(re.search(
        r"\b(lamar|lamaran|kirim cv|send cv|apply|application|rekrutmen|recruitment|career|talent acquisition|hrd?)\b",
        nearby,
    ))
    support_local = local in {"hello", "info", "support", "help", "admin", "contact", "care"}
    return apply_signal and not support_local


def _extract_email(soup: BeautifulSoup, description: str) -> str:
    for mailto in soup.select('a[href^="mailto:"]'):
        email = str(mailto.get("href", "")).split(":", 1)[-1].split("?", 1)[0].strip()
        parent_text = clean_html(mailto.parent or mailto)
        if _application_email(email, parent_text):
            return email
    for match in EMAIL_RE.finditer(description):
        start = max(0, match.start() - 120)
        end = min(len(description), match.end() + 120)
        if _application_email(match.group(0), description[start:end]):
            return match.group(0)
    return ""


def _generic_description(soup: BeautifulSoup, fallback_description: str) -> str:
    candidates: list[str] = []

    meta_description = soup.select_one('meta[name="description"]')
    if meta_description:
        candidates.append(clean_html(meta_description.get("content", "")))
    og_description = soup.select_one('meta[property="og:description"]')
    if og_description:
        candidates.append(clean_html(og_description.get("content", "")))
    if fallback_description:
        candidates.append(clean_html(fallback_description))

    selectors = (
        "[itemprop='description']",
        ".job-description",
        ".job_description",
        ".job-detail",
        ".job-details",
        ".vacancy-description",
        ".description",
        "article",
        "main",
    )
    for selector in selectors:
        for node in soup.select(selector)[:3]:
            text = clean_html(node)
            if 100 <= len(text) <= 30000:
                candidates.append(text)

    candidates = [value for value in candidates if value]
    if not candidates:
        return ""

    # Prefer the richest useful block, but cap output so navigation/footer noise
    # cannot create an unbounded application package.
    best = max(candidates, key=len)
    return best[:20000]


def parse_jobposting_html(
    html: str,
    url: str,
    source: str,
) -> list[Job]:
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[Job] = []

    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = script.string or script.get_text("", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue

        for item in _iter_jsonld(payload):
            if not _is_job_posting(item):
                continue
            title = clean_html(item.get("title"))
            company = _company_name(item.get("hiringOrganization"))
            description = clean_html(item.get("description"))
            location, remote = _location_text(item)
            source_job_id = _identifier_text(item.get("identifier"))
            job_url = str(item.get("url") or url).strip()
            if job_url:
                job_url = urljoin(url, job_url)
            apply_email = _extract_email(soup, description)

            if not title:
                continue
            if not company:
                company = urlsplit(job_url or url).netloc.removeprefix("www.")

            job = Job(
                title=title,
                company=company,
                location=location,
                url=job_url or url,
                description=description,
                source=source,
                apply_email=apply_email,
                posted_at=clean_html(item.get("datePosted", "")),
                source_job_id=source_job_id,
                employment_type=clean_html(item.get("employmentType")),
                salary=_salary_text(item.get("baseSalary")),
                remote=remote,
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


def _generic_title_score(value: str) -> int:
    text = clean_html(value)
    lowered = text.lower()
    if not text:
        return -100
    score = 0
    if re.search(r"\b(supervisor|manager|officer|executive|coordinator|team leader|sales|marketing|business development|management trainee|odp)\b", lowered):
        score += 4
    if re.search(r"\s[-|–—]\s", text):
        score += 2
    if re.search(r"\b(lowongan kerja terbaru|career development center|job portal|home page)\b", lowered):
        score -= 5
    if len(text) > 180:
        score -= 2
    return score


def parse_generic_job_page(
    html: str,
    url: str,
    source: str,
    fallback_title: str = "",
    fallback_description: str = "",
) -> Job | None:
    soup = BeautifulSoup(html, "html.parser")
    title_candidates: list[str] = []
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title:
        title_candidates.append(clean_html(og_title.get("content", "")))
    if soup.title:
        title_candidates.append(clean_html(soup.title.get_text(" ", strip=True)))
    if fallback_title:
        title_candidates.append(clean_html(fallback_title))
    title_candidates = [value for value in title_candidates if value]
    title = max(title_candidates, key=_generic_title_score) if title_candidates else ""

    description = _generic_description(soup, fallback_description)
    if not title or not description:
        return None

    company = urlsplit(url).netloc.removeprefix("www.") or "Unknown Company"
    apply_email = _extract_email(soup, description)
    job = Job(
        title=title,
        company=company,
        location="",
        url=url,
        description=description,
        source=source,
        apply_email=apply_email,
    )
    job.fingerprint = make_job_fingerprint(job.title, job.company, job.location, job.url)
    return job
