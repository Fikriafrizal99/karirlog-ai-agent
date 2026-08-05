from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_KEYS = {
    "fbclid",
    "gclid",
    "ref",
    "referrer",
    "source",
    "trk",
}


def normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9+#./-]+", value.lower()))


def canonicalize_url(url: str) -> str:
    value = url.strip()
    if not value:
        return ""
    try:
        parts = urlsplit(value)
    except ValueError:
        return value.lower()

    query = []
    for key, val in parse_qsl(parts.query, keep_blank_values=True):
        lower_key = key.lower()
        if lower_key.startswith("utm_") or lower_key in TRACKING_KEYS:
            continue
        query.append((key, val))

    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            urlencode(query, doseq=True),
            "",
        )
    )


def make_job_fingerprint(
    title: str,
    company: str,
    location: str,
    url: str = "",
    source_job_id: str = "",
) -> str:
    normalized_title = normalize_text(title)
    normalized_company = normalize_text(company)
    normalized_location = normalize_text(location)

    # Title + company + location intentionally becomes the primary key so the
    # same vacancy found through different search providers is collapsed.
    if normalized_title and normalized_company:
        base = f"semantic|{normalized_title}|{normalized_company}|{normalized_location}"
    elif source_job_id:
        base = f"source-id|{normalize_text(source_job_id)}"
    else:
        base = f"url|{canonicalize_url(url)}"

    return hashlib.sha256(base.encode("utf-8")).hexdigest()
