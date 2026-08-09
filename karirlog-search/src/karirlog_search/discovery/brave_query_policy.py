from __future__ import annotations

import math
import re
from typing import Any, Iterable

from .brave_source import (
    SOURCE_GROUP_LABELS,
    BraveSearchJobSource as _BaseBraveSearchJobSource,
)


class BraveSearchJobSource(_BaseBraveSearchJobSource):
    """Search policy for manual Search -> CSV -> Execution handoff.

    Query planning is split into configured search focuses. The Search engine
    still writes one shared CSV; focus labels only control how Brave query
    budget is allocated and are exposed in diagnostics.
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
        # clause would neutralise the preferred city/area list.
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

            if group in {"linkedin", "career_sites"}:
                query = f"{query} Indonesia"

            if active_locations:
                query = f"{query} ({self._quoted_or(active_locations)})"

            query = self._apply_detail_query_hint(query)
            normalized = re.sub(r"\s+", " ", query).strip()
            if self._query_within_brave_limits(normalized):
                return normalized, active_locations

            if active_locations:
                active_locations.pop()
                continue

            return "", []

    def _configured_focuses(self, fallback_roles: list[str]) -> list[dict[str, Any]]:
        configured = self.profile.get("search_focuses", [])
        target_lookup = {role.casefold(): role for role in fallback_roles}
        focuses: list[dict[str, Any]] = []
        seen_roles: set[str] = set()

        if isinstance(configured, list):
            for index, item in enumerate(configured):
                if not isinstance(item, dict):
                    continue
                focus_id = str(item.get("id") or f"FOCUS_{index + 1}").strip()
                label = str(item.get("label") or focus_id).strip()
                try:
                    weight = float(item.get("weight", 1.0))
                except (TypeError, ValueError):
                    weight = 1.0
                weight = max(0.0, weight)

                roles: list[str] = []
                for raw_role in item.get("roles", []):
                    marker = str(raw_role).strip().casefold()
                    canonical = target_lookup.get(marker)
                    if not canonical or marker in seen_roles:
                        continue
                    seen_roles.add(marker)
                    roles.append(canonical)

                if roles:
                    focuses.append(
                        {
                            "id": focus_id,
                            "label": label,
                            "weight": weight,
                            "roles": roles,
                        }
                    )

        uncovered = [
            role for role in fallback_roles if role.casefold() not in seen_roles
        ]
        if uncovered:
            focuses.append(
                {
                    "id": "UNASSIGNED",
                    "label": "Unassigned",
                    "weight": 0.0,
                    "roles": uncovered,
                }
            )

        if focuses:
            return focuses

        return [
            {
                "id": "ALL",
                "label": "All Roles",
                "weight": 1.0,
                "roles": list(fallback_roles),
            }
        ]

    @staticmethod
    def _allocate_focus_budgets(
        focuses: list[dict[str, Any]],
        total_budget: int,
    ) -> list[int]:
        if not focuses or total_budget <= 0:
            return []

        count = len(focuses)
        if total_budget < count:
            return [1 if index < total_budget else 0 for index in range(count)]

        weights = [max(0.0, float(item.get("weight", 0.0))) for item in focuses]
        if not any(weights):
            weights = [1.0] * count

        weight_sum = sum(weights)
        raw = [total_budget * weight / weight_sum for weight in weights]
        budgets = [max(1, math.floor(value)) for value in raw]

        while sum(budgets) > total_budget:
            candidates = [
                index for index, value in enumerate(budgets) if value > 1
            ]
            if not candidates:
                break
            index = min(
                candidates,
                key=lambda item: (raw[item] - math.floor(raw[item]), -item),
            )
            budgets[index] -= 1

        while sum(budgets) < total_budget:
            index = max(
                range(count),
                key=lambda item: (
                    raw[item] - math.floor(raw[item]),
                    weights[item],
                    -item,
                ),
            )
            budgets[index] += 1
            raw[index] = math.floor(raw[index])

        return budgets

    def _focus_queries(
        self,
        focus: dict[str, Any],
        focus_budget: int,
        groups: list[str],
        locations: list[str],
        configured_roles_per_query: int,
    ) -> list[str]:
        roles = self._dedupe_text(focus.get("roles", []))
        if not roles or focus_budget <= 0:
            return []

        roles_per_query = max(
            configured_roles_per_query,
            math.ceil(len(roles) / focus_budget),
        )
        chunks = [
            roles[index : index + roles_per_query]
            for index in range(0, len(roles), roles_per_query)
        ]

        output: list[str] = []
        seen_queries: set[str] = set()
        max_attempts = max(
            focus_budget * max(4, len(groups)),
            len(chunks) * len(groups) * 2,
        )

        for attempt in range(max_attempts):
            if len(output) >= focus_budget:
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
            if marker in seen_queries or marker in self.query_source_groups:
                continue
            seen_queries.add(marker)

            output.append(query)
            self.query_source_groups[marker] = group
            self.executed_query_plan.append(
                {
                    "focus": str(focus.get("id", "ALL")),
                    "focus_label": str(focus.get("label", "All Roles")),
                    "focus_weight": float(focus.get("weight", 1.0)),
                    "source": SOURCE_GROUP_LABELS.get(group, group),
                    "roles": list(chunks[chunk_index]),
                    "locations": list(used_locations),
                    "query": query,
                }
            )

        return output

    def _source_scoped_queries(self, roles: list[str], location_hint: str) -> list[str]:
        del location_hint

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

        total_budget = max(
            1,
            min(
                int(self.queries_per_run),
                int(self.max_search_requests_per_run),
            ),
        )
        focuses = self._configured_focuses(clean_roles)
        focus_budgets = self._allocate_focus_budgets(focuses, total_budget)
        configured_roles_per_query = max(
            1, int(self.config.get("roles_per_query", 4))
        )
        locations = self._preferred_location_terms()

        self.query_source_groups = {}
        self.executed_query_plan = []
        output: list[str] = []

        for focus, focus_budget in zip(focuses, focus_budgets):
            output.extend(
                self._focus_queries(
                    focus,
                    focus_budget,
                    groups,
                    locations,
                    configured_roles_per_query,
                )
            )

        return self._dedupe_queries(output)
