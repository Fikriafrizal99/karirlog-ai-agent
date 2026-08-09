from __future__ import annotations

import math
import re
from typing import Iterable

from .brave_source import (
    SOURCE_GROUP_LABELS,
    BraveSearchJobSource as _BaseBraveSearchJobSource,
)


class BraveSearchJobSource(_BaseBraveSearchJobSource):
    """Search policy for manual Search -> CSV -> Execution handoff.

    The legacy Brave collector remains responsible for parsing, hydration,
    validation, diagnostics, and deduplication. This subclass only replaces
    query planning so every configured target role gets search coverage and
    preferred locations are actually present in the Brave query.
    """

    @staticmethod
    def _dedupe_text(values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for raw in values:
            value = str(raw).strip()
            marker = value.casefold()
            if not value or marker in seen:
                continue
            seen.add(marker)
            output.append(value)
        return output

    def _preferred_location_terms(self) -> list[str]:
        values = self._dedupe_text(
            str(value)
            for value in self.profile.get("preferred_locations", [])
            if str(value).strip()
        )
        # Country localisation is already supplied through Brave's country
        # parameter/X-Loc headers. Keeping "Indonesia" inside an OR location
        # clause would make every specific city preference meaningless.
        return [value for value in values if value.casefold() != "indonesia"]

    @staticmethod
    def _quoted_or(values: list[str]) -> str:
        clean = [value.replace('"', "").strip() for value in values if value.strip()]
        return " OR ".join(f'"{value}"' for value in clean)

    def _fit_scoped_query(
        self,
        roles: list[str],
        source_filter: str,
        group: str,
        locations: list[str],
    ) -> tuple[str, list[str]]:
        active_locations = list(locations)
        role_group = self._quoted_or(roles)
        if not role_group:
            return "", []

        while True:
            query = f"({role_group}) {source_filter}".strip()

            # Global-looking sources benefit from an explicit Indonesia term,
            # while the OR location clause still narrows toward user preferences.
            if group in {"linkedin", "career_sites"}:
                query = f"{query} Indonesia"

            if active_locations:
                query = f"{query} ({self._quoted_or(active_locations)})"

            query = self._apply_detail_query_hint(query)
            normalized = re.sub(r"\s+", " ", query).strip()
            if self._query_within_brave_limits(normalized):
                return normalized, active_locations

            if active_locations:
                # Drop lowest-priority location terms from the tail until the
                # query fits Brave's 400-char / 50-word limits.
                active_locations.pop()
                continue

            # Four roles plus a source filter should fit. If a custom profile
            # somehow still exceeds limits, skip this candidate rather than
            # silently dropping a target role from coverage.
            return "", []

    def _source_scoped_queries(self, roles: list[str], location_hint: str) -> list[str]:
        del location_hint  # profile locations are handled explicitly below

        clean_roles = self._dedupe_text(roles)
        if not clean_roles:
            return []

        groups = [
            group
            for group in self.selected_source_groups
            if self._source_query_filter(group)
        ]
        if not groups:
            return []

        budget = max(
            1,
            min(
                int(self.queries_per_run),
                int(self.max_search_requests_per_run),
            ),
        )

        configured_roles_per_query = max(
            1, int(self.config.get("roles_per_query", 4))
        )
        minimum_for_full_coverage = max(1, math.ceil(len(clean_roles) / budget))
        roles_per_query = max(
            configured_roles_per_query,
            minimum_for_full_coverage,
        )

        chunks = [
            clean_roles[index : index + roles_per_query]
            for index in range(0, len(clean_roles), roles_per_query)
        ]
        locations = self._preferred_location_terms()

        output: list[str] = []
        seen_queries: set[str] = set()
        self.query_source_groups = {}
        self.executed_query_plan = []

        # First pass covers every role once. Remaining budget rotates the same
        # chunks through different source groups, improving recall without
        # exploding to every role x every source combination.
        max_attempts = max(budget * 4, len(chunks) * len(groups) * 2)
        for attempt in range(max_attempts):
            if len(output) >= budget:
                break

            chunk_index = attempt % len(chunks)
            cycle = attempt // len(chunks)
            group = groups[(chunk_index + cycle) % len(groups)]
            source_filter = self._source_query_filter(group)
            query, used_locations = self._fit_scoped_query(
                chunks[chunk_index],
                source_filter,
                group,
                locations,
            )
            if not query:
                continue

            marker = query.casefold()
            if marker in seen_queries:
                continue
            seen_queries.add(marker)

            output.append(query)
            self.query_source_groups[marker] = group
            self.executed_query_plan.append(
                {
                    "source": SOURCE_GROUP_LABELS.get(group, group),
                    "roles": list(chunks[chunk_index]),
                    "locations": list(used_locations),
                    "query": query,
                }
            )

        return self._dedupe_queries(output)
