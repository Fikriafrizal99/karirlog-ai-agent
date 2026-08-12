from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HttpClient:
    def __init__(self, config: dict[str, Any] | None = None):
        config = config or {}
        self.timeout = int(config.get("timeout_seconds", 20))
        self.user_agent = str(
            config.get(
                "user_agent",
                "KarirLog-AI-Agent/0.3 (+personal job discovery; respectful request rate)",
            )
        )
        retry_total = int(config.get("retry_total", 2))
        backoff = float(config.get("retry_backoff_seconds", 0.8))

        retry = Retry(
            total=retry_total,
            connect=retry_total,
            read=retry_total,
            status=retry_total,
            backoff_factor=backoff,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Language": "id-ID,id;q=0.9,en;q=0.7",
            }
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        timeout = kwargs.pop("timeout", self.timeout)
        response = self.session.get(url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response
