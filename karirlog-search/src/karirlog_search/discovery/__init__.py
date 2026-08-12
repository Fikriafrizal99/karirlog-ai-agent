"""Discovery package for the KarirLog Search Engine.

Copied verbatim from the legacy karirlog.discovery package; the only change is
that Job now comes from the shared karirlog_contracts package instead of a local
models module. Brave/RSS/URL/CSV collection, parsing, filtering and dedup logic
are unchanged.
"""

from .brave_source import BraveSearchJobSource
from .csv_source import CsvJobSource
from .manager import DiscoveryManager, export_discovery
from .results import CollectorReport, DiscoveryResult
from .rss_source import RssJobSource
from .url_source import UrlListJobSource

__all__ = [
    "BraveSearchJobSource",
    "CsvJobSource",
    "DiscoveryManager",
    "export_discovery",
    "CollectorReport",
    "DiscoveryResult",
    "RssJobSource",
    "UrlListJobSource",
]
