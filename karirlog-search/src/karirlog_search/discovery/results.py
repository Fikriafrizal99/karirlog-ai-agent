"""Discovery-internal result models (search side only).

These mirror the legacy karirlog.models CollectorReport / DiscoveryResult.
They are used only inside the discovery package, so they live here rather than
in the shared contracts package (which carries only Job + the CSV format).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from karirlog_contracts.job import Job


@dataclass(slots=True)
class CollectorReport:
    name: str
    collector_type: str
    status: str
    found: int = 0
    duration_ms: int = 0
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.collector_type,
            "status": self.status,
            "found": self.found,
            "duration_ms": self.duration_ms,
            "message": self.message,
        }


@dataclass(slots=True)
class DiscoveryResult:
    jobs: list[Job] = field(default_factory=list)
    reports: list[CollectorReport] = field(default_factory=list)
    raw_found: int = 0
    cross_source_duplicates: int = 0
    fallback_used: bool = False
