from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

import requests

from ..models import Job
from .base import JobSource
from .fingerprint import make_job_fingerprint
from .http_client import HttpClient
from .parsing import clean_html, parse_generic_job_page, parse_jobposting_html, repair_mojibake


PLATFORM_NAMES = {
    "jobstreet",
    "linkedin",
    "glassdoor",
    "glints",
    "indeed",
    "kitalulus",
    "dealls",
    "kalibrr",
    "jobsdb",
    "loker.id",
    "lokerjogja.id",
    "karir.com",
    "jobindo",
    "disnakerja",
}

LISTING_TEXT_PATTERNS = (
    r"\bfind your ideal job at\b",
    r"\btemukan pekerjaan ideal anda di\b",
    r"\bview all our .+ vacancies\b",
    r"\blihat semua .+ lowongan kami\b",
    r"^\s*\d+[\d.,+]*\s+(?:pekerjaan|jobs?)\s+.+\b(?:indonesia|baru)\b",
    r"\bjob openings?\b",
    r"\bdaftar lowongan\b",
)

CLOSED_JOB_PATTERNS = (
    r"\blowongan (?:ini )?(?:sudah|telah) ditutup\b",
    r"\blowongan (?:ini )?ditutup\b",
    r"\blowongan (?:ini )?(?:sudah )?tidak tersedia\b",
    r"\btidak lagi menerima lamaran\b",
    r"\bpendaftaran (?:sudah|telah) ditutup\b",
    r"\bjob (?:is )?(?:closed|expired)\b",
    r"\bposition (?:has been )?(?:filled|closed)\b",
    r"\bapplications? (?:are )?closed\b",
)

MONTHS = {
    "januari": 1,
    "january": 1,
    "jan": 1,
    "februari": 2,
    "february": 2,
    "feb": 2,
    "maret": 3,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "mei": 5,
    "may": 5,
    "juni": 6,
    "june": 6,
    "jun": 6,
    "juli": 7,
    "july": 7,
    "jul": 7,
    "agustus": 8,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "oktober": 10,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "desember": 12,
    "december": 12,
    "dec": 12,
}
MONTH_PATTERN = "|".join(sorted((re.escape(value) for value in MONTHS), key=len, reverse=True))



ROLE_TOKEN_STOPWORDS = {"and", "or", "the", "of", "for", "di", "dan", "yang"}
COMPANY_PREFIX_RE = re.compile(
    r"^(?:pt\.?|cv\.?|ud\.?|tbk\.?|persero|bank|bpr|group|holding|foundation|yayasan|universitas|university)\b",
    re.IGNORECASE,
)
INVALID_COMPANY_PATTERNS = (
    r"^\[?unlock with premium\]?$",
    r"^premium$",
    r"^confidential employer$",
    r"^n/?a$",
    r"^unknown$",
    r"^(?:karir|loker|lowongan|jobs?|career)[a-z0-9 ._-]*$",
)



SOURCE_GROUP_LABELS = {
    "kitalulus": "KitaLulus",
    "jobstreet": "Jobstreet",
    "linkedin": "LinkedIn",
    "kalibrr": "Kalibrr",
    "glints": "Glints",
    "career_sites": "Web Perusahaan/Universitas",
}

DEFAULT_SELECTED_SOURCE_GROUPS = tuple(SOURCE_GROUP_LABELS)

# Keep Brave queries concise. V18 placed eleven exact job titles in each query,
# which made every source query overly restrictive and produced almost no results.
# Two focused families cover the user's strongest, most realistic roles while the
# analyzer can still evaluate adjacent titles found in descriptions.
DEFAULT_SOURCE_ROLE_FAMILIES = (
    (
        "Sales Supervisor",
        "Marketing Supervisor",
        "Branch Manager",
        "Sales Coordinator",
        "Area Sales Supervisor",
    ),
    (
        "Account Officer",
        "Credit Marketing Officer",
        "Relationship Officer",
        "Account Executive",
        "Business Development Executive",
    ),
)

SELECTED_PORTAL_DOMAINS = {
    "kitalulus": ("kitalulus.com",),
    "jobstreet": ("jobstreet.com", "jobstreet.co.id"),
    "linkedin": ("linkedin.com",),
    "kalibrr": ("kalibrr.id", "kalibrr.com"),
    "glints": ("glints.com",),
}

# ATS-hosted company career pages are treated as the company-web source.
CAREER_ATS_DOMAINS = (
    "jobs.lever.co",
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.smartrecruiters.com",
    "apply.workable.com",
    "workable.com",
    "myworkdayjobs.com",
    "successfactors.com",
    "jobs.sap.com",
    "oraclecloud.com",
    "bamboohr.com",
    "recruitee.com",
    "teamtailor.com",
    "getredy.id",
)

# These are job aggregators/portals intentionally outside the user's six sources.
NON_SELECTED_JOB_PORTALS = (
    "indeed.com",
    "glassdoor.com",
    "dealls.com",
    "foundit.id",
    "foundit.com",
    "pintarnya.com",
    "bebee.com",
    "jobleads.com",
    "dailyremote.com",
    "disnakerja.com",
    "lokerjogja.id",
    "jakartakerja.com",
    "lokerbandung.id",
    "lokersemar.id",
    "sololoker.id",
    "karir.com",
    "jobsdb.com",
)

MULTI_POSITION_MARKERS = (
    r"\bdan beberapa posisi(?: lainnya)?\b",
    r"\bbeberapa posisi(?: lainnya)?\b",
    r"\bmultiple positions?\b",
    r"\bberbagai posisi\b",
)

DEFAULT_ROLE_ALIASES = {
    "Management Trainee": (
        "Officer Development Program",
        "ODP",
        "Management Development Program",
        "MDP",
        "Graduate Development Program",
    ),
    "Team Leader Sales": ("Sales Team Leader",),
    "Sales Operations": ("Sales Operation",),
    "Business Development": ("Business Development Representative", "BDR"),
}

FOREIGN_URL_PATTERNS = (
    r"/(?:us|usa|united-states)(?:/|$)",
    r"/(?:au|australia)(?:/|$)",
    r"/(?:gb|uk|united-kingdom)(?:/|$)",
    r"/(?:ca|canada)(?:/|$)",
    r"/(?:za|south-africa)(?:/|$)",
    r"united[-_]states",
    r"western[-_]cape",
    r"melbourne",
    r"bridgeport",
)

PORTAL_BOILERPLATE_PATTERNS = (
    r"jobleads:\s*finds jobs matched to your skills",
    r"the job platform genuinely on your side",
    r"unlock with premium",
)
FOREIGN_LOCATION_PATTERNS = (
    r"\bunited states\b", r"\busa\b", r"\bu\.s\.\b",
    r"(?:^|[,|/ ]+)us(?:$|[,|/ ]+)",
    r"\bcanada\b", r"\baustralia\b", r"\bunited kingdom\b", r"\buk\b", r"\bgb\b",
    r"(?:^|[,|/ ]+)(?:gb|au|ca|za)(?:$|[,|/ ]+)",
    r"\bsouth africa\b", r"\bcape town\b", r"\bwestern cape\b",
    r"\bmelbourne\b", r"\bsydney\b", r"\bbridgeport\b", r"\bchicago\b",
    r"\bnew york\b", r"\bcalifornia\b", r"\btexas\b", r"\bflorida\b",
    r"\bconnecticut\b", r"\bwestern australia\b", r"\bvictoria,? australia\b",
)
INDONESIA_LOCATION_RE = re.compile(
    r"\b(indonesia|jawa|jakarta|banten|bandung|bogor|bekasi|depok|tangerang|cianjur|sukabumi|cirebon|karawang|garut|semarang|surabaya|yogyakarta|jogja|blitar|bali|sumatra|kalimantan|sulawesi|papua|jabodetabek)\b",
    re.IGNORECASE,
)

DEFAULT_LOCATION_TERMS = (
    "Jawa Barat",
    "Jawa Tengah",
    "Jawa Timur",
    "DKI Jakarta",
    "Jakarta Selatan",
    "Jakarta Utara",
    "Jakarta Barat",
    "Jakarta Timur",
    "Jakarta Pusat",
    "Tangerang Selatan",
    "Tangerang",
    "Bekasi",
    "Bandung",
    "Bogor",
    "Depok",
    "Cianjur",
    "Sukabumi",
    "Cirebon",
    "Karawang",
    "Garut",
    "Banten",
    "Jabodetabek",
    "Semarang",
    "Surabaya",
    "Yogyakarta",
    "Indonesia",
)


class _CachedJsonResponse:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class BraveSearchJobSource(JobSource):
    ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    def __init__(
        self,
        config: dict[str, Any],
        profile: dict[str, Any],
        http: HttpClient,
        max_jobs: int = 100,
    ):
        self.config = config
        self.profile = profile
        self.http = http
        self.max_jobs = max_jobs
        self.api_key_env = str(config.get("api_key_env", "BRAVE_SEARCH_API_KEY"))
        self.api_key = os.getenv(self.api_key_env, "").strip()
        self.hydrate_pages = bool(config.get("hydrate_pages", True))
        self.results_per_query = min(20, max(1, int(config.get("results_per_query", 10))))
        self.queries_per_run = max(1, int(config.get("queries_per_run", 4)))
        self.country = str(config.get("country", "")).strip().upper()
        self.search_lang = str(config.get("search_lang", "")).strip().lower()
        self.ui_lang = str(config.get("ui_lang", "")).strip()
        self.freshness = str(config.get("freshness", "pw")).strip()
        self.location_country = str(config.get("location_country", self.country or "ID")).strip().upper()
        self.location_timezone = str(config.get("location_timezone", "Asia/Jakarta")).strip()
        self.search_pages_per_query = min(8, max(1, int(config.get("search_pages_per_query", 2))))
        self.max_search_requests_per_run = max(1, int(config.get("max_search_requests_per_run", 24)))
        self.max_hydration_attempts = max(1, int(config.get("max_hydration_attempts", 80)))
        self.expand_role_or_queries = bool(config.get("expand_role_or_queries", True))
        self.include_grouped_queries = bool(config.get("include_grouped_queries", False))
        self.prehydrate_min_score = max(1, int(config.get("prehydrate_min_score", 2)))
        self.extra_snippets = bool(config.get("extra_snippets", True))
        self.strict_detail_filter = bool(config.get("strict_detail_filter", True))
        self.max_explicit_age_days = max(
            1, int(config.get("max_explicit_age_days", 45))
        )
        self.min_description_chars = max(
            40, int(config.get("min_description_chars", 100))
        )
        self.require_location = bool(config.get("require_location", False))
        self.require_target_role_match = bool(config.get("require_target_role_match", True))
        self.role_match_min_ratio = float(config.get("role_match_min_ratio", 0.66))
        self.allow_global_remote = bool(config.get("allow_global_remote", False))
        self.reject_company_pages = bool(config.get("reject_company_pages", True))
        self.min_generic_description_chars = max(
            self.min_description_chars,
            int(config.get("min_generic_description_chars", self.min_description_chars)),
        )
        self.max_structured_jobs_per_page = max(
            1, int(config.get("max_structured_jobs_per_page", 10))
        )
        self.cache_enabled = bool(config.get("cache_enabled", False))
        self.cache_dir = Path(str(config.get("cache_dir", "data/cache/brave")))
        self.cache_ttl_hours = max(1, int(config.get("cache_ttl_hours", 24)))
        self.cache_only = bool(config.get("cache_only", False)) or (
            os.getenv("KARIRLOG_BRAVE_CACHE_ONLY", "").strip() == "1"
        )
        self.refresh_search_cache = bool(config.get("refresh_search_cache", False)) or (
            os.getenv("KARIRLOG_BRAVE_REFRESH_SEARCH", "").strip() == "1"
        )
        self.force_refresh_cache = bool(config.get("force_refresh_cache", False)) or (
            os.getenv("KARIRLOG_BRAVE_FORCE_REFRESH", "").strip() == "1"
        )
        self.detail_query_hint = str(config.get("detail_query_hint", "")).strip()
        self.listing_query_exclusions = str(config.get("listing_query_exclusions", "")).strip()
        self.generic_detail_min_score = max(2, int(config.get("generic_detail_min_score", 4)))
        self.custom_detail_url_patterns = [
            str(value).strip()
            for value in config.get("custom_detail_url_patterns", [])
            if str(value).strip()
        ]
        self.custom_listing_url_patterns = [
            str(value).strip()
            for value in config.get("custom_listing_url_patterns", [])
            if str(value).strip()
        ]
        self.role_aliases: dict[str, list[str]] = {
            key: list(values) for key, values in DEFAULT_ROLE_ALIASES.items()
        }
        for canonical, aliases in (config.get("role_aliases", {}) or {}).items():
            canonical_text = str(canonical).strip()
            if not canonical_text:
                continue
            if isinstance(aliases, str):
                alias_values = [aliases]
            else:
                alias_values = list(aliases or [])
            clean_aliases = [str(value).strip() for value in alias_values if str(value).strip()]
            if clean_aliases:
                self.role_aliases.setdefault(canonical_text, []).extend(clean_aliases)
        configured_source_groups = [
            str(value).strip().lower()
            for value in config.get("selected_source_groups", DEFAULT_SELECTED_SOURCE_GROUPS)
            if str(value).strip().lower() in SOURCE_GROUP_LABELS
        ]
        self.selected_source_groups = tuple(
            configured_source_groups or DEFAULT_SELECTED_SOURCE_GROUPS
        )
        self.source_scoped_queries = bool(config.get("source_scoped_queries", True))
        self.preferred_parameter_mode = str(
            config.get("brave_parameter_mode", "")
        ).strip().lower()
        configured_families = (
            config.get("source_role_families")
            or config.get("source_query_families")
            or DEFAULT_SOURCE_ROLE_FAMILIES
        )
        self.source_role_families: list[list[str]] = []
        for family in configured_families:
            if isinstance(family, str):
                values = [family]
            else:
                values = list(family or [])
            clean_values = [str(value).strip() for value in values if str(value).strip()]
            if clean_values:
                self.source_role_families.append(clean_values[:6])
        if not self.source_role_families:
            self.source_role_families = [list(values) for values in DEFAULT_SOURCE_ROLE_FAMILIES]
        self.source_group_counts: Counter[str] = Counter()
        self.search_results_by_source: Counter[str] = Counter()
        self.query_source_groups: dict[str, str] = {}
        self.query_diagnostics: list[dict[str, Any]] = []
        self.executed_query_plan: list[dict[str, Any]] = []
        self.allowed_domains = {
            str(domain).lower().removeprefix("www.")
            for domain in config.get("allowed_domains", [])
            if domain
        }
        self.excluded_domains = {
            str(domain).lower().removeprefix("www.")
            for domain in config.get("excluded_domains", [])
            if domain
        }
        self.warnings: list[str] = []
        self.filter_counts: Counter[str] = Counter()
        self.retry_count = 0
        self.search_results_seen = 0
        self.search_pages_requested = 0
        self.search_requests_used = 0
        self.hydration_attempts = 0
        self.generated_queries = 0
        self.parameter_mode = ""
        self._working_parameter_mode: str | None = None
        self.search_cache_hits = 0
        self.page_cache_hits = 0
        self.search_api_calls = 0
        self.page_network_calls = 0
        self.legacy_query_cache_hits = 0
        self.response_countries: Counter[str] = Counter()
        self.rejection_samples: list[dict[str, str]] = []
        self.diagnostics_path = Path(
            str(config.get("diagnostics_path", "data/output/latest_discovery_diagnostics.json"))
        )
        self.summary_message = "Collector selesai"

    def readiness(self) -> tuple[bool, str]:
        if self.cache_only:
            return True, "Ready from cache"
        if not self.api_key:
            return False, f"Environment {self.api_key_env} belum diisi"
        return True, "Ready"

    def _cache_path(self, kind: str, key: str, suffix: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8", errors="ignore")).hexdigest()
        return self.cache_dir / kind / f"{digest}.{suffix}"

    def _cache_fresh(self, path: Path, *, kind: str = "page") -> bool:
        if not path.exists() or self.force_refresh_cache:
            return False
        # Live Update must always fetch fresh Brave search results, while it may
        # still reuse recently cached job-detail pages. Full Refresh bypasses both.
        if kind == "search" and self.refresh_search_cache and not self.cache_only:
            return False
        age_seconds = max(0.0, time.time() - path.stat().st_mtime)
        return age_seconds <= self.cache_ttl_hours * 3600

    def _read_json_cache(self, key: str) -> dict[str, Any] | None:
        if not self.cache_enabled:
            return None
        path = self._cache_path("search", key, "json")
        if not self._cache_fresh(path, kind="search"):
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        self.search_cache_hits += 1
        return payload if isinstance(payload, dict) else None

    def _read_legacy_query_cache(self, query: str) -> dict[str, Any] | None:
        """Read an older cached response by its original query.

        V14 localizes new Brave requests with country=ID. Existing V13 caches were
        created without country, so their hash differs. Cache-only diagnostics may
        still reuse them safely without making a network request. Normal live runs
        never use this fallback.
        """
        if self.source_scoped_queries:
            return None
        if not self.cache_enabled or not self.cache_only:
            return None
        search_dir = self.cache_dir / "search"
        if not search_dir.exists():
            return None
        query_marker = re.sub(r"\s+", " ", query).strip().casefold()
        quoted = re.search(r'"([^"]+)"', query)
        role_marker = self._normalized_role_text(quoted.group(1)) if quoted else ""
        candidates = sorted(
            search_dir.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in candidates:
            if not self._cache_fresh(path, kind="search"):
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            original = str((payload.get("query") or {}).get("original", ""))
            original_marker = re.sub(r"\s+", " ", original).strip().casefold()
            if original_marker != query_marker:
                original_quoted = re.search(r'"([^"]+)"', original)
                original_role = (
                    self._normalized_role_text(original_quoted.group(1))
                    if original_quoted else ""
                )
                if not role_marker or original_role != role_marker:
                    continue
            self.search_cache_hits += 1
            self.legacy_query_cache_hits += 1
            return payload if isinstance(payload, dict) else None
        return None

    def _write_json_cache(self, key: str, payload: dict[str, Any]) -> None:
        if not self.cache_enabled:
            return
        path = self._cache_path("search", key, "json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _read_page_cache(self, url: str) -> str | None:
        if not self.cache_enabled:
            return None
        path = self._cache_path("pages", url, "html")
        if not self._cache_fresh(path, kind="page"):
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        self.page_cache_hits += 1
        return text

    def _write_page_cache(self, url: str, html: str) -> None:
        if not self.cache_enabled or not html:
            return
        path = self._cache_path("pages", url, "html")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8", errors="ignore")

    def _get_page_html(self, url: str) -> str:
        cached = self._read_page_cache(url)
        if cached is not None:
            return cached
        if self.cache_only:
            return ""
        response = self.http.get(url)
        self.page_network_calls += 1
        html = response.text
        self._write_page_cache(url, html)
        return html

    def _apply_detail_query_hint(self, query: str) -> str:
        value = query.strip()
        if self.detail_query_hint and "site:" not in value.lower():
            value = f"{value} {self.detail_query_hint}".strip()
        if self.listing_query_exclusions:
            value = f"{value} {self.listing_query_exclusions}".strip()
        return value

    @staticmethod
    def _split_first_or_group(query: str) -> list[str]:
        """Split the first parenthesized OR group into individual search queries.

        User queries commonly group several roles in the first parentheses and
        locations in the last parentheses. Splitting only the first group keeps
        the location constraint while giving Brave one clear job title per query.
        """
        for match in re.finditer(r"\(([^()]*)\)", query):
            group = match.group(1)
            if not re.search(r"\s+OR\s+", group, re.IGNORECASE):
                continue
            values = []
            for raw in re.split(r"\s+OR\s+", group, flags=re.IGNORECASE):
                value = raw.strip().strip('"').strip("'").strip()
                if value:
                    values.append(value)
            # A role group normally contains specific multiword titles. Avoid
            # splitting generic keyword groups such as lowongan OR jobs.
            generic = {"lowongan", "loker", "karir", "jobs", "job", "vacancy", "vacancies", "hiring"}
            if len(values) < 2 or all(value.lower() in generic for value in values):
                continue
            prefix = query[: match.start()]
            suffix = query[match.end() :]
            return [f'{prefix}"{value}"{suffix}'.strip() for value in values]
        return []

    @staticmethod
    def _dedupe_queries(queries: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for query in queries:
            normalized = re.sub(r"\s+", " ", query).strip()
            marker = normalized.casefold()
            if normalized and marker not in seen:
                seen.add(marker)
                output.append(normalized)
        return output

    @staticmethod
    def _domain_matches(domain: str, patterns: tuple[str, ...] | list[str] | set[str]) -> bool:
        return any(domain == value or domain.endswith(f".{value}") for value in patterns)

    @staticmethod
    def _is_university_domain(domain: str) -> bool:
        return bool(
            domain.endswith(".ac.id")
            or domain.endswith(".edu")
            or re.search(r"\.edu\.[a-z]{2,3}$", domain)
        )

    @classmethod
    def _career_url_evidence(cls, url: str) -> bool:
        parsed = urlsplit(url)
        domain = parsed.netloc.lower().removeprefix("www.")
        path = unquote(parsed.path.lower())
        query_keys = {key.lower() for key in parse_qs(parsed.query)}
        if cls._domain_matches(domain, CAREER_ATS_DOMAINS):
            return True
        if cls._is_university_domain(domain) and re.search(
            r"/(?:cdc|career|careers|karir|lowongan|jobs?|vacanc|rekrut|alumni|kemahasiswaan)(?:/|$)",
            path,
        ):
            return True
        if re.search(
            r"/(?:career|careers|karir|jobs?|job-detail|vacancies|vacancy|recruitment|rekrutmen|openings?|positions?|opportunities|lowongan)(?:/|$)",
            path,
        ):
            return True
        return bool(
            query_keys
            & {
                "jobid", "job_id", "job", "reqid", "req_id", "requisitionid",
                "vacancyid", "vacancy_id", "positionid", "position_id", "gh_jid",
            }
        )

    def _source_group_for_url(
        self,
        url: str,
        *,
        page_html: str = "",
    ) -> str:
        domain = self._domain(url)
        if not domain:
            return ""
        for group, domains in SELECTED_PORTAL_DOMAINS.items():
            if group in self.selected_source_groups and self._domain_matches(domain, domains):
                return group
        if self._domain_matches(domain, NON_SELECTED_JOB_PORTALS):
            return ""
        if "career_sites" not in self.selected_source_groups:
            return ""
        if self._career_url_evidence(url):
            return "career_sites"
        html_lower = page_html.lower()
        if page_html and "jobposting" in html_lower and "application/ld+json" in html_lower:
            return "career_sites"
        return ""

    def _source_query_filter(self, group: str) -> str:
        # Brave officially recommends starting with simple operator combinations.
        # Use domains only here; URL-detail validation still happens after search.
        if group == "kitalulus":
            return "site:kitalulus.com"
        if group == "jobstreet":
            return "site:id.jobstreet.com"
        if group == "linkedin":
            return "site:linkedin.com"
        if group == "kalibrr":
            return "(site:kalibrr.id OR site:kalibrr.com)"
        if group == "glints":
            return "site:glints.com"
        if group == "career_sites":
            # Official company ATS pages and Indonesian university career centers.
            return (
                "(site:ac.id OR site:getredy.id OR site:jobs.lever.co "
                "OR site:boards.greenhouse.io OR site:jobs.smartrecruiters.com "
                "OR site:myworkdayjobs.com OR site:successfactors.com)"
            )
        return ""

    @staticmethod
    def _query_within_brave_limits(query: str) -> bool:
        # Brave Web Search currently limits q to 400 characters and 50 words.
        return len(query) <= 400 and len(query.split()) <= 50

    def _source_scoped_queries(self, roles: list[str], location_hint: str) -> list[str]:
        if not roles:
            return []

        target_lookup = {self._normalized_role_text(value): value for value in roles}
        role_families: list[list[str]] = []
        for configured_family in self.source_role_families[:2]:
            active: list[str] = []
            for role in configured_family:
                marker = self._normalized_role_text(role)
                if marker in target_lookup:
                    active.append(target_lookup[marker])
                elif role in {"Team Leader Sales", "Business Development Executive"}:
                    # Keep common aliases searchable when the profile uses the
                    # equivalent canonical title. Validation still checks profile.
                    active.append(role)
            if active:
                role_families.append(active[:5])

        if not role_families:
            # Conservative fallback for a custom profile: two small chunks, never
            # the eleven-title mega queries generated by V18.
            compact = roles[:10]
            role_families = [compact[:5], compact[5:10]]
            role_families = [family for family in role_families if family]

        output: list[str] = []
        self.query_source_groups = {}
        self.executed_query_plan = []
        for group in self.selected_source_groups:
            source_filter = self._source_query_filter(group)
            if not source_filter:
                continue
            for family_index, role_family in enumerate(role_families, start=1):
                active_roles = list(role_family)
                while active_roles:
                    role_group = " OR ".join(f'"{role}"' for role in active_roles)
                    # Country is already supplied through the API parameter and
                    # X-Loc headers. Only global sources need an Indonesia word.
                    country_hint = " Indonesia" if group in {"linkedin", "career_sites"} else ""
                    query = f"({role_group}) {source_filter}{country_hint}"
                    query = self._apply_detail_query_hint(query)
                    normalized = re.sub(r"\s+", " ", query).strip()
                    if self._query_within_brave_limits(normalized):
                        break
                    active_roles.pop()
                if not active_roles:
                    continue
                output.append(normalized)
                self.query_source_groups[normalized.casefold()] = group
                self.executed_query_plan.append(
                    {
                        "source": SOURCE_GROUP_LABELS.get(group, group),
                        "family": family_index,
                        "roles": list(active_roles),
                        "query": normalized,
                    }
                )
        return self._dedupe_queries(output)

    def _queries(self) -> list[str]:
        configured = [str(value).strip() for value in self.config.get("queries", []) if value]
        if configured:
            expanded: list[str] = []
            for value in configured:
                split = self._split_first_or_group(value) if self.expand_role_or_queries else []
                if split:
                    expanded.extend(split)
                    if self.include_grouped_queries:
                        expanded.append(value)
                else:
                    expanded.append(value)
            queries = self._dedupe_queries(expanded)[: self.queries_per_run]
            self.generated_queries = len(queries)
            return [self._apply_detail_query_hint(value) for value in queries]

        roles = [str(value).strip() for value in self.profile.get("target_roles", []) if value]
        locations = [
            str(value).strip()
            for value in self.profile.get("preferred_locations", [])
            if value
        ]
        priority_locations = [
            value for value in locations
            if value.lower() in {
                "jawa barat", "banten", "jabodetabek", "jakarta",
                "remote", "hybrid", "indonesia",
            }
        ]
        selected_locations = (priority_locations or locations)[:7]
        location_hint = " OR ".join(f'"{value}"' for value in selected_locations)

        if self.source_scoped_queries:
            queries = self._source_scoped_queries(roles, location_hint)[: self.queries_per_run]
            self.generated_queries = len(queries)
            return queries

        suffix = str(
            self.config.get(
                "query_suffix",
                '(lowongan OR loker OR karir OR jobs OR vacancy OR hiring) -course -training',
            )
        )
        queries = []
        for role in roles[: self.queries_per_run]:
            query = f'"{role}" {suffix}'
            if location_hint:
                query += f" ({location_hint})"
            queries.append(self._apply_detail_query_hint(query))
        queries = self._dedupe_queries(queries)
        self.generated_queries = len(queries)
        return queries

    def _domain_allowed(self, url: str) -> bool:
        domain = urlsplit(url).netloc.lower().removeprefix("www.")
        if not domain:
            return False
        if any(domain == value or domain.endswith(f".{value}") for value in self.excluded_domains):
            return False
        if self.allowed_domains and not any(
            domain == value or domain.endswith(f".{value}") for value in self.allowed_domains
        ):
            return False
        return bool(self._source_group_for_url(url))

    @staticmethod
    def _domain(url: str) -> str:
        return urlsplit(url).netloc.lower().removeprefix("www.")

    @classmethod
    def _is_known_detail_url(cls, url: str) -> bool:
        parsed = urlsplit(url)
        domain = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.lower().rstrip("/")
        query = parse_qs(parsed.query)

        if "kitalulus.com" in domain:
            return "/lowongan/detail/" in path
        if "jobstreet." in domain:
            return bool(re.search(r"/(?:id/)?job/\d+(?:$|[-/])", path))
        if "linkedin.com" in domain:
            return bool(re.search(r"/jobs/view/\d+", path))
        if "glints.com" in domain:
            return "/opportunities/jobs/" in path
        if "glassdoor." in domain:
            return "/job-listing/" in path or "jl" in query
        if "indeed." in domain:
            return path.endswith("/viewjob") or bool(query.get("jk"))
        if "dealls.com" in domain:
            return "/loker/" in path and len(path.split("/")) >= 4
        if "kalibrr." in domain:
            return bool(re.search(r"/c/.+/jobs/\d+", path))
        if domain == "jobs.lever.co" or domain.endswith(".jobs.lever.co"):
            return len([part for part in path.split("/") if part]) >= 2
        if domain == "boards.greenhouse.io" or domain.endswith(".boards.greenhouse.io"):
            return "/jobs/" in path
        if "workable.com" in domain:
            return "/j/" in path or "/view/" in path

        # Company career sites usually use a job-specific slug or ID after these segments.
        return bool(
            re.search(
                r"/(?:jobs?|careers?|vacancies?|vacancy|lowongan|loker)/(?:detail/|view/)?[^/]{4,}$",
                path,
            )
        )

    @classmethod
    def _is_listing_url(cls, url: str) -> bool:
        parsed = urlsplit(url)
        domain = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.lower().rstrip("/")
        query = parse_qs(parsed.query)

        if cls._is_known_detail_url(url):
            return False
        if "jobstreet." in domain:
            return bool(
                re.search(r"(?:^|/)(?:id/)?[^/]*(?:\+|-)?jobs(?:/in-[^/]+)?$", path)
                or path in {"", "/jobs", "/id/jobs"}
            )
        if "linkedin.com" in domain:
            return path.startswith("/jobs")
        if "glints.com" in domain:
            return "/job-category/" in path or path.endswith("/jobs")
        if "indeed." in domain:
            return any(key in query for key in ("q", "l")) or path.startswith("/q-")
        if "glassdoor." in domain:
            return "/job/" in path and "/job-listing/" not in path

        last = path.rsplit("/", 1)[-1]
        return last in {
            "jobs",
            "job",
            "careers",
            "career",
            "vacancies",
            "vacancy",
            "lowongan",
            "search",
            "job-search",
            "job-board",
            "opportunities",
        }

    @staticmethod
    def _matches_url_patterns(url: str, patterns: list[str]) -> bool:
        for pattern in patterns:
            try:
                if re.search(pattern, url, re.IGNORECASE):
                    return True
            except re.error:
                continue
        return False

    def _is_listing_candidate(self, url: str) -> bool:
        return self._is_listing_url(url) or self._matches_url_patterns(
            url, self.custom_listing_url_patterns
        )

    def _generic_detail_score(
        self,
        url: str,
        title: str,
        description: str,
        page_html: str = "",
    ) -> int:
        parsed = urlsplit(url)
        path = parsed.path.lower().rstrip("/")
        query = {key.lower() for key in parse_qs(parsed.query)}
        score = 0

        # A specific job-like path is a strong signal, regardless of portal domain.
        if re.search(
            r"/(?:jobs?|careers?|vacancies?|vacancy|lowongan|loker|positions?|openings?|opportunities|requisitions?)/(?:detail/|view/)?[^/]{4,}$",
            path,
        ):
            score += 2
        if any(
            key in query
            for key in {
                "jobid", "job_id", "job", "jk", "jl", "vacancyid",
                "vacancy_id", "reqid", "req_id", "requisitionid",
                "gh_jid", "positionid", "position_id",
            }
        ):
            score += 2

        slug = path.rsplit("/", 1)[-1]
        if re.match(
            r"(?:lowongan(?:-kerja)?|loker|rekrutmen|karir|career|hiring|open-recruitment)[-_].{6,}",
            slug,
            re.IGNORECASE,
        ):
            score += 2

        if title and not self._looks_like_listing_text(title, ""):
            score += 1
        if len(clean_html(description)) >= self.min_description_chars:
            score += 1

        html_lower = page_html.lower()
        if "application/ld+json" in html_lower and "jobposting" in html_lower:
            score += 4
        if re.search(
            r"\b(apply now|apply for this job|lamar sekarang|kirim lamaran|ajukan lamaran)\b",
            html_lower,
        ):
            score += 2
        if re.search(
            r"\b(job description|deskripsi pekerjaan|responsibilities|tanggung jawab|qualifications|kualifikasi)\b",
            f"{title} {description} {clean_html(page_html[:8000])}",
            re.IGNORECASE,
        ):
            score += 1
        return score

    def _is_detail_candidate(
        self,
        url: str,
        title: str,
        description: str,
        page_html: str = "",
    ) -> bool:
        if self._is_known_detail_url(url):
            return True
        if self._matches_url_patterns(url, self.custom_detail_url_patterns):
            return True
        return (
            self._generic_detail_score(url, title, description, page_html)
            >= self.generic_detail_min_score
        )

    @staticmethod
    def _looks_like_listing_text(title: str, description: str) -> bool:
        text = f"{title} {description}".lower()
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in LISTING_TEXT_PATTERNS)

    @staticmethod
    def _looks_closed(text: str) -> bool:
        value = clean_html(text).lower()
        return any(re.search(pattern, value, re.IGNORECASE) for pattern in CLOSED_JOB_PATTERNS)

    @classmethod
    def _portal_aliases(cls, url: str) -> set[str]:
        domain = cls._domain(url)
        aliases = set(PLATFORM_NAMES)
        if domain:
            aliases.add(domain)
            aliases.add(domain.removeprefix("id."))
            first = domain.split(".", 1)[0]
            if first:
                aliases.add(first)
                aliases.add(f"{first}.id")
        return {value.lower().strip() for value in aliases if value}

    @classmethod
    def _clean_company_candidate(cls, value: str, url: str) -> str:
        candidate = clean_html(value).strip(" -|,–—")
        aliases = sorted(cls._portal_aliases(url), key=len, reverse=True)
        for alias in aliases:
            candidate = re.sub(
                rf"\s*[|–—-]\s*{re.escape(alias)}\s*$",
                "",
                candidate,
                flags=re.IGNORECASE,
            ).strip(" -|,–—")
        return candidate[:120]

    @staticmethod
    def _normalized_role_text(value: str) -> str:
        text = repair_mojibake(clean_html(value)).casefold()
        text = text.replace("&", " and ")
        return re.sub(r"[^a-z0-9]+", " ", text).strip()

    @classmethod
    def _role_tokens(cls, value: str) -> set[str]:
        return {
            token
            for token in cls._normalized_role_text(value).split()
            if len(token) > 1 and token not in ROLE_TOKEN_STOPWORDS
        }

    def _role_variants(self) -> list[tuple[str, str]]:
        variants: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        targets = [
            str(value).strip()
            for value in self.profile.get("target_roles", [])
            if str(value).strip()
        ]
        for canonical in targets:
            for variant in [canonical, *self.role_aliases.get(canonical, [])]:
                marker = (canonical.casefold(), str(variant).strip().casefold())
                if marker in seen or not marker[1]:
                    continue
                seen.add(marker)
                variants.append((canonical, str(variant).strip()))
        return variants

    def _matches_target_role(self, title: str) -> bool:
        title_norm = self._normalized_role_text(title)
        title_tokens = self._role_tokens(title)
        if not title_norm or not title_tokens:
            return False
        variants = self._role_variants()
        if not variants:
            return True

        for _canonical, variant in variants:
            variant_norm = self._normalized_role_text(variant)
            if variant_norm and re.search(rf"\b{re.escape(variant_norm)}\b", title_norm):
                return True
            variant_tokens = self._role_tokens(variant)
            if len(variant_tokens) < 2:
                continue
            overlap = len(title_tokens & variant_tokens)
            ratio = overlap / len(variant_tokens)
            if overlap >= 2 and ratio >= self.role_match_min_ratio:
                return True
        return False

    def _target_role_matches(self, text: str) -> list[str]:
        evidence_norm = self._normalized_role_text(text)
        if not evidence_norm:
            return []
        evidence_tokens = set(evidence_norm.split())
        matches: list[tuple[int, int, int, str]] = []
        for canonical, variant in self._role_variants():
            variant_norm = self._normalized_role_text(variant)
            variant_tokens = self._role_tokens(variant)
            if not variant_norm or not variant_tokens:
                continue
            exact = bool(re.search(rf"\b{re.escape(variant_norm)}\b", evidence_norm))
            overlap = len(variant_tokens & evidence_tokens)
            ratio = overlap / len(variant_tokens)
            if exact or (len(variant_tokens) >= 2 and overlap >= 2 and ratio >= 0.8):
                matches.append((1 if exact else 0, len(variant_tokens), len(variant_norm), canonical))
        matches.sort(reverse=True)
        output: list[str] = []
        for _, _, _, canonical in matches:
            if canonical not in output:
                output.append(canonical)
        return output

    def _exact_target_role_matches(self, text: str) -> list[str]:
        evidence_norm = self._normalized_role_text(text)
        if not evidence_norm:
            return []
        matches: list[tuple[int, int, str]] = []
        for canonical, variant in self._role_variants():
            variant_norm = self._normalized_role_text(variant)
            if variant_norm and re.search(rf"\b{re.escape(variant_norm)}\b", evidence_norm):
                matches.append((len(variant_norm.split()), len(variant_norm), canonical))
        matches.sort(reverse=True)
        output: list[str] = []
        for _, _, canonical in matches:
            if canonical in output:
                continue
            canonical_norm = self._normalized_role_text(canonical)
            # A specific role wins over its parent role: Area Sales Supervisor
            # should not also become Sales Supervisor; BDE should not also become
            # the broader Business Development role.
            if any(
                canonical_norm != self._normalized_role_text(selected)
                and re.search(
                    rf"\b{re.escape(canonical_norm)}\b",
                    self._normalized_role_text(selected),
                )
                for selected in output
            ):
                continue
            output.append(canonical)
        return output

    def _best_target_role(self, text: str) -> str:
        matches = self._target_role_matches(text)
        return matches[0] if matches else ""

    def _normalize_title_role(self, title: str, company: str = "") -> tuple[str, str]:
        value = clean_html(title).strip(" -|,–—")
        company_value = clean_html(company).strip(" -|,–—")
        if company_value:
            value = re.sub(
                rf"\s*[|–—-]\s*{re.escape(company_value)}\s*$",
                "",
                value,
                flags=re.IGNORECASE,
            ).strip(" -|,–—")

        exact_roles = self._exact_target_role_matches(value)
        if len(exact_roles) > 1:
            return value, "ambiguous_multi_position"
        if not exact_roles:
            return value, "role_not_target"

        separators = len(re.findall(r"(?:\s[-|–—,]\s|/)", value))
        noisy_prefix = bool(re.match(r"^(?:info )?loker\b|^lowongan kerja\b|^solo posisi\b", value, re.I))
        multi_marker = any(re.search(pattern, value, re.I) for pattern in MULTI_POSITION_MARKERS)
        if separators >= 1 or multi_marker or noisy_prefix:
            return exact_roles[0], "accepted"
        return value[:180], "accepted"

    def _company_from_page_title(self, title: str, url: str) -> str:
        candidate = self._clean_company_candidate(title, url)
        if not candidate or self._matches_target_role(candidate):
            return ""
        if COMPANY_PREFIX_RE.search(candidate) or re.search(
            r"\b(group|holding|company|corporation|corp\.?|inc\.?|ltd\.?|tbk\.?|persero)\b",
            candidate,
            re.IGNORECASE,
        ):
            return candidate[:120]
        return ""

    def _company_from_role_title(self, title: str, role: str, url: str) -> str:
        clean_title = clean_html(title).strip()
        if not clean_title or not role:
            return ""
        role_pattern = re.escape(clean_html(role).strip())
        patterns = (
            rf"^{role_pattern}\s*[|–—-]\s*(.+)$",
            rf"^(.+?)\s*[|–—-]\s*{role_pattern}(?:\s*[|–—-].*)?$",
            rf"^{role_pattern}\s+(?:at|di)\s+(.+)$",
        )
        for pattern in patterns:
            match = re.match(pattern, clean_title, re.IGNORECASE)
            if not match:
                continue
            candidate = self._clean_company_candidate(match.group(1), url)
            if candidate and not self._matches_target_role(candidate):
                return candidate[:120]
        return ""

    @classmethod
    def _company_from_evidence(cls, text: str, url: str) -> str:
        value = clean_html(text)
        patterns = (
            r"\b((?:PT\.?|CV\.?|Bank|BPR)\s+[A-Z0-9][A-Za-z0-9&.,'()\- ]{2,100}?(?:Tbk\.?|\(Persero\)|Persero)?)\s+(?:membuka|sedang membuka|mengundang|menawarkan|mencari|recruiting|hiring)\b",
            r"\b(?:di|at)\s+((?:PT\.?|CV\.?|Bank|BPR)\s+[A-Z0-9][A-Za-z0-9&.,'()\- ]{2,100}?)(?:[.,]|$)",
        )
        for pattern in patterns:
            match = re.search(pattern, value, re.IGNORECASE)
            if match:
                candidate = cls._clean_company_candidate(match.group(1), url)
                if candidate:
                    return candidate[:120]
        return ""

    def _looks_like_company_page(self, title: str, company: str) -> bool:
        title_norm = self._normalized_role_text(title)
        company_norm = self._normalized_role_text(company)
        if not title_norm:
            return True
        if title_norm == company_norm:
            return True
        if COMPANY_PREFIX_RE.search(clean_html(title)) and not self._matches_target_role(title):
            return True
        return False

    def _location_allowed(self, job: Job, page_text: str = "") -> bool:
        if self.allow_global_remote:
            return True

        # Lokasi terstruktur harus menjadi sumber utama. Jangan biarkan kata
        # "Indonesia" dari footer/deskripsi menimpa lokasi eksplisit Chicago/US.
        explicit_location = clean_html(job.location)
        explicit_indonesia = bool(INDONESIA_LOCATION_RE.search(explicit_location))
        explicit_foreign = any(
            re.search(pattern, explicit_location, re.IGNORECASE)
            for pattern in FOREIGN_LOCATION_PATTERNS
        )
        if explicit_foreign and not explicit_indonesia:
            return False
        if explicit_indonesia:
            return True

        url_text = unquote(job.url).replace("_", "-").lower()
        if any(re.search(pattern, url_text, re.IGNORECASE) for pattern in FOREIGN_URL_PATTERNS):
            return False

        # Hanya gunakan bagian awal deskripsi; footer global tidak ikut menilai lokasi.
        evidence = clean_html(f"{job.title} {job.description[:1000]}")
        indonesia_signal = bool(INDONESIA_LOCATION_RE.search(f"{explicit_location} {evidence} {url_text}"))
        foreign_signal = any(
            re.search(pattern, f"{explicit_location} {evidence}", re.IGNORECASE)
            for pattern in FOREIGN_LOCATION_PATTERNS
        )
        if foreign_signal and not indonesia_signal:
            return False
        return True

    @staticmethod
    def _looks_like_portal_boilerplate(description: str) -> bool:
        value = clean_html(description).lower()
        return any(re.search(pattern, value, re.IGNORECASE) for pattern in PORTAL_BOILERPLATE_PATTERNS)

    @classmethod
    def _stale_title_or_url_date(cls, title: str, url: str) -> date | None:
        text = clean_html(f"{title} {url}").lower()
        explicit = cls._explicit_date(text)
        if explicit:
            return explicit
        path = urlsplit(url).path
        year_month_match = re.search(r"/(20\d{2})/(0?[1-9]|1[0-2])(?:/|$)", path)
        if year_month_match:
            try:
                return date(int(year_month_match.group(1)), int(year_month_match.group(2)), 1)
            except ValueError:
                pass
        year_match = re.search(r"\b(?:tahun|anggaran|year)\s*(20\d{2})\b", text)
        if not year_match:
            year_match = re.search(r"(?:^|[-_/])(20\d{2})(?:[-_/]|$)", path)
        if year_match:
            try:
                return date(int(year_match.group(1)), 1, 1)
            except ValueError:
                return None
        return None

    @classmethod
    def _normalize_title_and_company(cls, title: str, url: str) -> tuple[str, str]:
        clean_title = clean_html(title).strip()
        patterns = (
            r"^lowongan kerja\s+(.+?)\s+di\s+(.+)$",
            r"^(.+?)\s+membuka lowongan\s+(.+)$",
            r"^(.+?)\s+hiring\s+(.+?)(?:\s+job\s+in\s+.+)?$",
        )
        for index, pattern in enumerate(patterns):
            match = re.match(pattern, clean_title, re.IGNORECASE)
            if not match:
                continue
            if index == 0:
                role, company = match.group(1), match.group(2)
            else:
                company, role = match.group(1), match.group(2)
            role = clean_html(role).strip(" -|,–—")
            company = cls._clean_company_candidate(company, url)
            if role and company:
                return role[:180], company
        return clean_title[:180], ""

    @classmethod
    def _guess_company(cls, title: str, url: str) -> str:
        normalized_title, normalized_company = cls._normalize_title_and_company(title, url)
        if normalized_company:
            return normalized_company
        clean_title = normalized_title
        domain = cls._domain(url)

        patterns = (
            r"^(.+?)\s+hiring\s+.+?\s+job\s+in\s+.+?(?:\s*[|–—-]\s*glassdoor)?$",
            r"^(.+?)\s+(?:sedang mencari|membuka lowongan)\s+.+?(?:\s*[|–—-]\s*linkedin)?$",
            r"\bjobs?\s+at\s+(.+?)(?:\s*[|,–—-]|$)",
            r"\b(?:job|lowongan kerja)\s+.+?\s+(?:at|di)\s+(.+?)(?:\s*[|–—-]\s*(?:jobstreet|glints|kitalulus|dealls)|$)",
        )
        for pattern in patterns:
            match = re.search(pattern, clean_title, re.IGNORECASE)
            if match:
                candidate = cls._clean_company_candidate(match.group(1), url)
                if candidate and candidate.lower() not in PLATFORM_NAMES:
                    return candidate[:120]

        parts = [part.strip() for part in re.split(r"\s[-|–—]\s", clean_title) if part.strip()]
        while parts and parts[-1].lower() in PLATFORM_NAMES:
            parts.pop()
        if len(parts) >= 2:
            candidate = cls._clean_company_candidate(parts[-1], url)
            if candidate.lower() not in PLATFORM_NAMES:
                return candidate[:120]

        if domain == "jobs.lever.co":
            path_parts = [part for part in urlsplit(url).path.split("/") if part]
            if path_parts:
                return path_parts[0].replace("-", " ").title()[:120]
        if domain == "boards.greenhouse.io":
            path_parts = [part for part in urlsplit(url).path.split("/") if part]
            if path_parts:
                return path_parts[0].replace("-", " ").title()[:120]
        return ""

    def _infer_location(self, title: str, description: str) -> tuple[str, bool]:
        # Remote hanya diakui bila muncul di judul atau dekat awal deskripsi.
        # Ini mencegah footer/daftar lowongan lain menambahkan Remote secara palsu.
        title_text = clean_html(title)
        description_head = clean_html(description)[:800]
        text = f"{title_text} {description_head}"
        remote = bool(re.search(r"\b(remote|work from home|wfh|telecommute)\b", title_text, re.I))
        if not remote:
            remote = bool(re.search(
                r"\b(?:lokasi kerja|penempatan|work location|work arrangement|sistem kerja|jenis kerja)\b\s*[:=\-]?\s*(?:full[- ]?time\s+)?\b(remote|work from home|wfh|telecommute)\b",
                description_head,
                re.IGNORECASE,
            ))
        configured = [
            str(value).strip()
            for value in self.profile.get("preferred_locations", [])
            if value and str(value).strip().lower() not in {"remote", "hybrid"}
        ]
        terms = list(dict.fromkeys(configured + list(DEFAULT_LOCATION_TERMS)))
        found = [term for term in terms if re.search(rf"\b{re.escape(term)}\b", text, re.I)]
        found = sorted(dict.fromkeys(found), key=len, reverse=True)
        specific = [value for value in found if value.lower() != "indonesia"]
        selected = (specific or found)[:3]
        if remote and "Remote" not in selected:
            selected.insert(0, "Remote")
        return " | ".join(selected), remote

    @classmethod
    def _posted_date_from_text(cls, text: str) -> date | None:
        value = clean_html(text)
        labels = (
            r"date posted", r"posted(?: on)?", r"published(?: on)?",
            r"tanggal tayang", r"tanggal posting", r"diposting", r"ditayangkan",
        )
        for label in labels:
            match = re.search(rf"\b(?:{label})\b.{{0,80}}", value, re.IGNORECASE)
            if match:
                parsed = cls._explicit_date(match.group(0))
                if parsed:
                    return parsed
        return None

    @staticmethod
    def _explicit_date(text: str, today: date | None = None) -> date | None:
        today = today or date.today()
        value = clean_html(text).lower()
        if not value:
            return None

        iso_match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", value)
        if iso_match:
            try:
                return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
            except ValueError:
                pass

        full_match = re.search(
            rf"\b(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})\b",
            value,
            re.IGNORECASE,
        )
        if full_match:
            try:
                return date(
                    int(full_match.group(3)),
                    MONTHS[full_match.group(2).lower()],
                    int(full_match.group(1)),
                )
            except (KeyError, ValueError):
                pass

        relative = re.search(
            r"\b(\d{1,3})\s+(hari|days?|minggu|weeks?|bulan|months?|tahun|years?)\s+(?:yang lalu|ago)\b",
            value,
        )
        if relative:
            amount = int(relative.group(1))
            unit = relative.group(2).lower()
            if unit.startswith(("hari", "day")):
                days = amount
            elif unit.startswith(("minggu", "week")):
                days = amount * 7
            elif unit.startswith(("bulan", "month")):
                days = amount * 30
            else:
                days = amount * 365
            return today - timedelta(days=days)
        if re.search(r"\b(hari ini|today)\b", value):
            return today

        month_match = re.search(
            rf"\b({MONTH_PATTERN})\s+(20\d{{2}})\b",
            value,
            re.IGNORECASE,
        )
        if month_match:
            try:
                return date(int(month_match.group(2)), MONTHS[month_match.group(1).lower()], 1)
            except (KeyError, ValueError):
                pass
        return None

    def _normalize_job_metadata(self, job: Job, page_text: str = "") -> Job:
        normalized_title, normalized_company = self._normalize_title_and_company(job.title, job.url)
        job.title = normalized_title
        if normalized_company:
            job.company = normalized_company
        else:
            job.company = self._clean_company_candidate(job.company, job.url)

        job.title, _ = self._normalize_title_role(job.title, job.company)

        if not job.location:
            job.location, inferred_remote = self._infer_location(job.title, job.description)
            job.remote = job.remote or inferred_remote

        posted = self._explicit_date(job.posted_at)
        if not posted:
            posted = self._posted_date_from_text(page_text)
        if posted and posted <= date.today():
            job.posted_at = posted.isoformat()
        elif posted and posted > date.today():
            job.posted_at = ""
        return job

    @staticmethod
    def _valid_company(company: str, url: str) -> bool:
        value = clean_html(company).strip(" .,-|_").lower()
        if not value or value in {"unknown company", "indonesia"}:
            return False
        if value in PLATFORM_NAMES:
            return False
        if any(re.fullmatch(pattern, value, re.IGNORECASE) for pattern in INVALID_COMPANY_PATTERNS):
            return False
        if not COMPANY_PREFIX_RE.search(value) and re.search(
            r"\b(?:portal|info loker|lowongan kerja|karir(?:jakarta|jogja|bandung|solo)?|loker(?:jogja|bandung|semar|solo)?)\b",
            value,
            re.IGNORECASE,
        ):
            return False
        domain = BraveSearchJobSource._domain(url)
        if value in {domain, domain.removeprefix("id.")}:
            return False
        if re.fullmatch(r"(?:january|february|march|april|may|june|july|august|september|october|november|december|januari|februari|maret|mei|juni|juli|agustus|oktober|desember)\s+20\d{2}", value):
            return False
        return True

    def _validate_job(
        self,
        job: Job,
        *,
        structured: bool,
        page_text: str = "",
    ) -> tuple[bool, str]:
        combined_text = f"{job.title} {job.description} {page_text}"
        source_group = self._source_group_for_url(job.url, page_html=page_text)
        if not source_group:
            return False, "source_not_selected"
        job.source = SOURCE_GROUP_LABELS[source_group]
        if self._is_listing_url(job.url) or self._looks_like_listing_text(job.title, job.description):
            return False, "listing_or_category"
        if self._looks_closed(combined_text):
            return False, "closed"
        if self.reject_company_pages and self._looks_like_company_page(job.title, job.company):
            return False, "company_page"
        if self.require_target_role_match:
            normalized_title, title_reason = self._normalize_title_role(job.title, job.company)
            if title_reason != "accepted":
                return False, title_reason
            job.title = normalized_title
        if not self._location_allowed(job, page_text):
            return False, "foreign_location"
        if self._looks_like_portal_boilerplate(job.description):
            return False, "portal_boilerplate"
        if not self._valid_company(job.company, job.url):
            return False, "invalid_company"
        minimum_description = (
            self.min_description_chars if structured else self.min_generic_description_chars
        )
        if len(clean_html(job.description)) < minimum_description:
            return False, "insufficient_description"
        posted_date = self._explicit_date(job.posted_at)
        if posted_date and posted_date > date.today():
            job.posted_at = ""
            posted_date = None
        content_date = self._stale_title_or_url_date(job.title, job.url)
        for explicit in (posted_date, content_date):
            if explicit and explicit <= date.today() and (date.today() - explicit).days > self.max_explicit_age_days:
                return False, "stale"
        if self.require_location and not job.location and not job.remote:
            return False, "missing_location"
        return True, "accepted"

    def _params_for_mode(self, query: str, offset: int, mode: str) -> dict[str, Any]:
        params: dict[str, Any] = {
            "q": query,
            "count": self.results_per_query,
            "offset": offset,
        }
        if mode in {"full", "without_extra", "localized_minimal"}:
            if self.country:
                params["country"] = self.country
            if self.search_lang:
                params["search_lang"] = self.search_lang
            if self.ui_lang:
                params["ui_lang"] = self.ui_lang
            if self.freshness:
                params["freshness"] = self.freshness
            if mode in {"full", "without_extra"}:
                params["safesearch"] = "moderate"
            if mode == "full" and self.extra_snippets:
                params["extra_snippets"] = "true"
        elif mode == "country_only":
            if self.country:
                params["country"] = self.country
            if self.freshness:
                params["freshness"] = self.freshness
        elif mode == "freshness_only" and self.freshness:
            params["freshness"] = self.freshness
        return params

    def _search_response(
        self,
        query: str,
        headers: dict[str, str],
        *,
        offset: int = 0,
    ):
        modes = [
            "full",
            "without_extra",
            "localized_minimal",
            "country_only",
            "freshness_only",
            "minimal",
        ]
        preferred_mode = self._working_parameter_mode or self.preferred_parameter_mode
        if preferred_mode in modes:
            modes = [preferred_mode] + [
                mode for mode in modes if mode != preferred_mode
            ]

        unique_attempts: list[tuple[str, dict[str, Any]]] = []
        seen = set()
        for mode in modes:
            params = self._params_for_mode(query, offset, mode)
            marker = tuple(sorted((key, str(value)) for key, value in params.items()))
            if marker in seen:
                continue
            seen.add(marker)
            unique_attempts.append((mode, params))

        last_error: Exception | None = None
        for mode, params in unique_attempts:
            cache_key = json.dumps(params, ensure_ascii=False, sort_keys=True)
            cached_payload = self._read_json_cache(cache_key)
            if cached_payload is not None:
                self._working_parameter_mode = mode
                self.parameter_mode = f"{mode}/cache"
                return _CachedJsonResponse(cached_payload)
            if self.cache_only:
                continue
            try:
                response = self.http.get(self.ENDPOINT, params=params, headers=headers)
                self.search_api_calls += 1
                payload = response.json()
                self._write_json_cache(cache_key, payload)
                self._working_parameter_mode = mode
                self.parameter_mode = mode
                return _CachedJsonResponse(payload)
            except requests.HTTPError as exc:
                status_code = getattr(exc.response, "status_code", None)
                if status_code != 422:
                    raise
                self.retry_count += 1
                last_error = exc
                if mode == self._working_parameter_mode:
                    self._working_parameter_mode = None

        legacy = self._read_legacy_query_cache(query)
        if legacy is not None:
            self.parameter_mode = "legacy-query/cache"
            return _CachedJsonResponse(legacy)
        if last_error:
            raise last_error
        if self.cache_only:
            raise RuntimeError("Cache Brave belum tersedia untuk query ini. Jalankan collect_live.bat sekali.")
        raise RuntimeError("Brave Search tidak mengembalikan respons")

    def _record_filter(
        self,
        reason: str,
        *,
        url: str = "",
        title: str = "",
        company: str = "",
    ) -> None:
        self.filter_counts[reason] += 1
        if url and len(self.rejection_samples) < 200:
            self.rejection_samples.append(
                {
                    "reason": reason,
                    "title": clean_html(title)[:240],
                    "company": clean_html(company)[:160],
                    "url": url,
                }
            )

    def _write_diagnostics(self, jobs: list[Job]) -> None:
        payload = {
            "accepted_count": len(jobs),
            "accepted": [
                {
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "posted_at": job.posted_at,
                    "url": job.url,
                    "description_length": len(clean_html(job.description)),
                    "source": job.source,
                }
                for job in jobs
            ],
            "active_source_groups": [
                {"id": group, "label": SOURCE_GROUP_LABELS[group]}
                for group in self.selected_source_groups
            ],
            "accepted_by_source": dict(self.source_group_counts),
            "filter_counts": dict(self.filter_counts),
            "rejected": self.rejection_samples,
            "search": {
                "queries": self.generated_queries,
                "results_seen": self.search_results_seen,
                "results_by_source": {
                    SOURCE_GROUP_LABELS.get(group, group): count
                    for group, count in self.search_results_by_source.items()
                },
                "query_plan": self.executed_query_plan,
                "query_details": self.query_diagnostics,
                "api_calls": self.search_api_calls,
                "search_cache_hits": self.search_cache_hits,
                "page_cache_hits": self.page_cache_hits,
                "response_countries": dict(self.response_countries),
                "parameter_mode": self.parameter_mode,
            },
            "warnings": self.warnings,
        }
        try:
            self.diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
            self.diagnostics_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            if len(self.warnings) < 10:
                self.warnings.append(f"Gagal menulis diagnostik discovery: {exc}")

    @classmethod
    def _semantic_job_key(cls, job: Job) -> tuple[str, str, str]:
        title = cls._normalized_role_text(job.title)
        company = cls._normalized_role_text(job.company)
        location = cls._normalized_role_text(job.location)
        location_tokens = [
            token for token in location.split()
            if token not in {"remote", "hybrid", "id", "indonesia"}
        ]
        return title, company, " ".join(location_tokens)

    def _dedupe_semantic_jobs(self, jobs: list[Job]) -> list[Job]:
        output: list[Job] = []
        seen: set[tuple[str, str, str]] = set()
        for job in jobs:
            key = self._semantic_job_key(job)
            if key in seen:
                self._record_filter(
                    "semantic_duplicate",
                    url=job.url,
                    title=job.title,
                    company=job.company,
                )
                continue
            seen.add(key)
            output.append(job)
        return output

    def _finalize_summary(self, jobs: list[Job]) -> None:
        accepted = len(jobs)
        parts = [
            f"Collector selesai; {accepted} detail lowongan lolos",
            f"hasil Brave diperiksa={self.search_results_seen}",
            f"query dijalankan={self.generated_queries}",
            f"request pencarian={self.search_requests_used}/{self.max_search_requests_per_run}",
            f"halaman pencarian={self.search_pages_requested}",
            f"halaman detail dibaca={self.hydration_attempts}/{self.max_hydration_attempts}",
            f"API Brave baru={self.search_api_calls}",
            f"cache pencarian={self.search_cache_hits}",
            f"cache halaman={self.page_cache_hits}",
        ]
        if self.legacy_query_cache_hits:
            parts.append(f"cache query lama={self.legacy_query_cache_hits}")
        if self.search_results_by_source:
            source_results = ",".join(
                f"{SOURCE_GROUP_LABELS.get(group, group)}:{count}"
                for group, count in self.search_results_by_source.items()
            )
            parts.append(f"hasil sumber={source_results}")
        if self.response_countries:
            countries = ",".join(
                f"{country}:{count}" for country, count in self.response_countries.most_common()
            )
            parts.append(f"negara hasil={countries}")
        filtered = sum(self.filter_counts.values())
        if filtered:
            labels = {
                "listing_or_category": "listing/kategori",
                "not_detail_url": "URL bukan detail",
                "invalid_company": "perusahaan tidak valid",
                "insufficient_description": "deskripsi kurang",
                "stale": "data lama",
                "missing_location": "lokasi kosong",
                "closed": "lowongan ditutup",
                "company_page": "halaman perusahaan",
                "role_not_target": "posisi tidak sesuai target",
                "foreign_location": "lokasi luar negeri",
                "portal_boilerplate": "deskripsi portal",
                "embedded_job_list": "daftar lowongan tertanam",
                "embedded_job_list_trimmed": "daftar tertanam dipotong",
                "weak_search_candidate": "kandidat pencarian lemah",
                "hydration_limit": "batas pembacaan halaman",
                "source_not_selected": "sumber di luar 6 pilihan",
            }
            detail = ", ".join(
                f"{labels.get(reason, reason)}={count}"
                for reason, count in self.filter_counts.most_common()
            )
            parts.append(f"{filtered} ditahan ({detail})")
        if self.parameter_mode:
            parts.append(f"parameter Brave={self.parameter_mode}")
        if self.retry_count:
            parts.append(f"retry 422={self.retry_count}")
        if self.warnings:
            parts.append(f"warning halaman={len(self.warnings)}")
        self.summary_message = "; ".join(parts)
        self._write_diagnostics(jobs)

    def collect(self) -> list[Job]:
        ready, message = self.readiness()
        if not ready:
            raise RuntimeError(message)

        jobs: list[Job] = []
        seen_urls: set[str] = set()
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        if self.location_country:
            headers["X-Loc-Country"] = self.location_country
        if self.location_timezone:
            headers["X-Loc-Timezone"] = self.location_timezone

        queries = self._queries()
        for query in queries:
            if len(jobs) >= self.max_jobs or self.search_requests_used >= self.max_search_requests_per_run:
                break
            query_group = self.query_source_groups.get(query.casefold(), "unknown")

            for offset in range(self.search_pages_per_query):
                if (
                    len(jobs) >= self.max_jobs
                    or self.search_requests_used >= self.max_search_requests_per_run
                ):
                    break
                response = self._search_response(query, headers, offset=offset)
                self.search_requests_used += 1
                self.search_pages_requested += 1
                payload = response.json()
                response_country = str((payload.get("query") or {}).get("country", "")).upper()
                if response_country:
                    self.response_countries[response_country] += 1
                results = payload.get("web", {}).get("results", [])
                result_count = len(results)
                if query_group != "unknown":
                    self.search_results_by_source[query_group] += result_count
                self.query_diagnostics.append(
                    {
                        "source": SOURCE_GROUP_LABELS.get(query_group, query_group),
                        "query": query,
                        "page": offset + 1,
                        "results": result_count,
                        "country": response_country,
                    }
                )
                if not results:
                    break

                self.search_results_seen += result_count
                new_urls_on_page = 0

                for item in results:
                    if len(jobs) >= self.max_jobs:
                        break
                    url = str(item.get("url", "")).strip()
                    if not url or url in seen_urls:
                        continue
                    if not self._domain_allowed(url):
                        self._record_filter("source_not_selected", url=url)
                        continue
                    seen_urls.add(url)
                    new_urls_on_page += 1

                    result_title = clean_html(item.get("title", ""))
                    snippets = [item.get("description", "")]
                    snippets.extend(item.get("extra_snippets", []) or [])
                    result_description = clean_html(" ".join(str(value) for value in snippets if value))
                    result_posted_at = clean_html(item.get("page_age") or item.get("age") or "")

                    listing_candidate = self._is_listing_candidate(url) or self._looks_like_listing_text(
                        result_title, result_description
                    )
                    result_source_group = self._source_group_for_url(url)
                    # Selected portals sometimes expose several structured
                    # JobPosting records on a search page. Hydrate those pages
                    # first; if no structured detail is found, reject later.
                    allow_structured_listing = bool(
                        listing_candidate
                        and result_source_group in {
                            "kitalulus", "jobstreet", "linkedin", "kalibrr", "glints"
                        }
                    )
                    if listing_candidate and not allow_structured_listing:
                        self._record_filter("listing_or_category", url=url, title=result_title)
                        continue

                    normalized_result_title, _ = self._normalize_title_and_company(
                        result_title, url
                    )
                    role_evidence = self._best_target_role(
                        f"{normalized_result_title} {result_title} {result_description} {url}"
                    )
                    has_target_roles = any(
                        str(value).strip() for value in self.profile.get("target_roles", [])
                    )
                    if self.require_target_role_match and has_target_roles and not role_evidence:
                        self._record_filter("role_not_target", url=url, title=result_title)
                        continue

                    # Search broadly, but hydrate only candidates that already look
                    # job-specific from their URL/title/snippet. This keeps a high-volume
                    # run useful without opening hundreds of generic pages.
                    known_detail = self._is_known_detail_url(url) or self._matches_url_patterns(
                        url, self.custom_detail_url_patterns
                    )
                    prehydrate_score = self._generic_detail_score(
                        url, result_title, result_description
                    )
                    if not known_detail and prehydrate_score < self.prehydrate_min_score:
                        self._record_filter("weak_search_candidate", url=url, title=result_title)
                        continue

                    page_html = ""
                    parsed_jobs: list[Job] = []
                    if self.hydrate_pages:
                        if self.hydration_attempts >= self.max_hydration_attempts:
                            self._record_filter("hydration_limit", url=url, title=result_title)
                            continue
                        self.hydration_attempts += 1
                        try:
                            page_html = self._get_page_html(url)
                            if page_html:
                                parsed_jobs = parse_jobposting_html(page_html, url, "Brave Search")
                        except Exception as exc:
                            if len(self.warnings) < 10:
                                self.warnings.append(f"Gagal membaca {url}: {exc}")

                    if parsed_jobs:
                        if len(parsed_jobs) > self.max_structured_jobs_per_page:
                            if self.max_structured_jobs_per_page == 1:
                                self._record_filter("embedded_job_list", url=url, title=result_title)
                                continue
                            self._record_filter("embedded_job_list_trimmed", url=url, title=result_title)
                        for parsed_job in parsed_jobs[: self.max_structured_jobs_per_page]:
                            page_text = clean_html(page_html)
                            parsed_job = self._normalize_job_metadata(parsed_job, page_text)
                            accepted, reason = self._validate_job(
                                parsed_job, structured=True, page_text=page_text
                            )
                            if not accepted:
                                self._record_filter(
                                    reason, url=parsed_job.url, title=parsed_job.title, company=parsed_job.company
                                )
                                continue
                            source_group = self._source_group_for_url(parsed_job.url, page_html=page_html)
                            parsed_job.source = SOURCE_GROUP_LABELS.get(source_group, parsed_job.source)
                            self.source_group_counts[parsed_job.source] += 1
                            jobs.append(parsed_job)
                            if len(jobs) >= self.max_jobs:
                                break
                        continue

                    if listing_candidate:
                        self._record_filter("listing_or_category", url=url, title=result_title)
                        continue

                    if self.strict_detail_filter and not self._is_detail_candidate(
                        url, result_title, result_description, page_html
                    ):
                        self._record_filter("not_detail_url", url=url, title=result_title)
                        continue

                    generic = None
                    if page_html:
                        generic = parse_generic_job_page(
                            page_html,
                            url,
                            "Brave Search",
                            fallback_title=result_title,
                            fallback_description=result_description,
                        )
                    title = generic.title if generic else result_title
                    description = generic.description if generic else result_description
                    apply_email = generic.apply_email if generic else ""
                    if role_evidence and not self._matches_target_role(title) and self._matches_target_role(result_title):
                        title = result_title
                    if not title or not description:
                        self._record_filter("insufficient_description", url=url, title=title)
                        continue

                    page_text = clean_html(page_html)
                    original_title = title
                    normalized_title, normalized_company = self._normalize_title_and_company(title, url)
                    title_roles = self._exact_target_role_matches(
                        f"{normalized_title} {result_title}"
                    )
                    role_hint = title_roles[0] if len(title_roles) == 1 else ""
                    # Body evidence is only a fallback for true company-page titles.
                    if not role_hint and self._looks_like_company_page(normalized_title, normalized_company):
                        body_roles = self._exact_target_role_matches(
                            f"{result_description} {description[:3000]}"
                        )
                        role_hint = body_roles[0] if len(body_roles) == 1 else ""
                    if role_hint and not self._matches_target_role(normalized_title):
                        normalized_title = role_hint
                    role_company = (
                        self._company_from_role_title(result_title, role_hint, url)
                        or self._company_from_role_title(original_title, role_hint, url)
                    )
                    if role_company and role_hint:
                        normalized_title = role_hint
                    company = (
                        normalized_company
                        or role_company
                        or self._company_from_evidence(result_description, url)
                        or self._company_from_evidence(description[:3000], url)
                        or self._company_from_page_title(original_title, url)
                        or self._guess_company(original_title, url)
                    )
                    location, remote = self._infer_location(normalized_title, description)
                    posted_date = self._explicit_date(result_posted_at)
                    if not posted_date and page_html:
                        posted_date = self._posted_date_from_text(page_text)
                    if posted_date and posted_date > date.today():
                        posted_date = None
                    job = Job(
                        title=normalized_title,
                        company=company,
                        location=location,
                        url=url,
                        description=description,
                        source="Brave Search",
                        apply_email=apply_email,
                        posted_at=posted_date.isoformat() if posted_date else "",
                        remote=remote,
                    )
                    accepted, reason = self._validate_job(
                        job, structured=False, page_text=page_text
                    )
                    if not accepted:
                        self._record_filter(reason, url=job.url, title=job.title, company=job.company)
                        continue
                    job.fingerprint = make_job_fingerprint(
                        job.title, job.company, job.location, job.url
                    )
                    self.source_group_counts[job.source] += 1
                    jobs.append(job)

                if new_urls_on_page == 0 or len(results) < self.results_per_query:
                    break

        jobs = self._dedupe_semantic_jobs(jobs)
        self.source_group_counts = Counter(job.source for job in jobs)
        self._finalize_summary(jobs)
        return jobs
