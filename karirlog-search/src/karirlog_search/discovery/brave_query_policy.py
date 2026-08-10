from __future__ import annotations

import json
import math
import re
from typing import Any, Iterable

from .brave_source import (
    _CachedJsonResponse,
    BraveSearchJobSource as _BaseBraveSearchJobSource,
)


PORTAL_SEARCH_FILTER = (
    "(site:kitalulus.com OR site:id.jobstreet.com OR site:linkedin.com "
    "OR site:glints.com OR site:kalibrr.com OR site:kalibrr.id)"
)


class BraveSearchJobSource(_BaseBraveSearchJobSource):
    """High-recall Brave query policy for manual Search -> CSV handoff.

    The budget is allocated by configured search focus (currently 7 Core +
    5 General for a 12-request run). Queries search several selected portals
    at once instead of locking every request to one portal/location. The last
    query of each focus is intentionally broad so official career/ATS pages can
    still be discovered. Final URL/source/role/location validation remains in
    the base collector before a job reaches the CSV.
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

    @staticmethod
    def _quoted_or(values: list[str]) -> str:
        clean = [value.replace('"', "").strip() for value in values if value.strip()]
        return " OR ".join(f'"{value}"' for value in clean)

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
            candidates = [index for index, value in enumerate(budgets) if value > 1]
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

    @staticmethod
    def _balanced_chunks(roles: list[str], budget: int) -> list[list[str]]:
        if not roles or budget <= 0:
            return []
        chunk_count = min(len(roles), budget)
        base, remainder = divmod(len(roles), chunk_count)
        chunks: list[list[str]] = []
        cursor = 0
        for index in range(chunk_count):
            size = base + (1 if index < remainder else 0)
            chunks.append(roles[cursor : cursor + size])
            cursor += size
        return chunks

    def _fit_high_recall_query(
        self,
        roles: list[str],
        *,
        portal_scoped: bool,
    ) -> str:
        active_roles = list(roles)
        while active_roles:
            role_group = self._quoted_or(active_roles)
            query = f"({role_group})" if len(active_roles) > 1 else role_group
            if portal_scoped:
                query = f"{query} {PORTAL_SEARCH_FILTER}"
            query = self._apply_detail_query_hint(query)
            normalized = re.sub(r"\s+", " ", query).strip()
            if self._query_within_brave_limits(normalized):
                return normalized

            # Prefer keeping every role and dropping the portal union before
            # sacrificing role coverage because final source validation is strict.
            if portal_scoped:
                portal_scoped = False
                continue
            active_roles.pop()
        return ""

    def _focus_queries(
        self,
        focus: dict[str, Any],
        focus_budget: int,
    ) -> list[str]:
        roles = self._dedupe_text(focus.get("roles", []))
        chunks = self._balanced_chunks(roles, focus_budget)
        if not chunks:
            return []

        output: list[str] = []
        for index, chunk in enumerate(chunks):
            # One broad-web request per focus preserves discovery of official
            # company/university/ATS career pages. The rest target all selected
            # job portals in one query to maximise usable results per API call.
            portal_scoped = index < len(chunks) - 1
            query = self._fit_high_recall_query(chunk, portal_scoped=portal_scoped)
            if not query:
                continue
            output.append(query)
            self.executed_query_plan.append(
                {
                    "focus": str(focus.get("id", "ALL")),
                    "focus_label": str(focus.get("label", "All Roles")),
                    "focus_weight": float(focus.get("weight", 1.0)),
                    "source": "Selected portals" if portal_scoped else "Broad web",
                    "roles": list(chunk),
                    "locations": [],
                    "query": query,
                }
            )
        return output

    def _source_scoped_queries(self, roles: list[str], location_hint: str) -> list[str]:
        # Location preference is enforced during result validation. Country=ID and
        # X-Loc headers already localise Brave, so adding every city to q only
        # reduces recall and previously caused 12 successful requests with 0 hits.
        del location_hint

        clean_roles = self._dedupe_text(roles)
        if not clean_roles:
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

        self.query_source_groups = {}
        self.executed_query_plan = []
        output: list[str] = []
        for focus, focus_budget in zip(focuses, focus_budgets):
            output.extend(self._focus_queries(focus, focus_budget))

        return self._dedupe_queries(output)[:total_budget]

    def _search_response(
        self,
        query: str,
        headers: dict[str, str],
        *,
        offset: int = 0,
    ):
        """Perform at most one Brave network call for one logical search page.

        The previous parameter-fallback loop could make several paid network
        calls for one logical request when Brave returned 422. We already use a
        verified conservative mode (country_only), so fail fast and let the
        outer collector/fallback handle an invalid request without exceeding the
        configured network-call budget.
        """
        mode = self._working_parameter_mode or self.preferred_parameter_mode
        if mode not in {
            "full",
            "without_extra",
            "localized_minimal",
            "country_only",
            "freshness_only",
            "minimal",
        }:
            mode = "country_only"

        params = self._params_for_mode(query, offset, mode)
        cache_key = json.dumps(params, ensure_ascii=False, sort_keys=True)
        cached_payload = self._read_json_cache(cache_key)
        if cached_payload is not None:
            self._working_parameter_mode = mode
            self.parameter_mode = f"{mode}/cache"
            return _CachedJsonResponse(cached_payload)

        if self.cache_only:
            legacy = self._read_legacy_query_cache(query)
            if legacy is not None:
                self.parameter_mode = "legacy-query/cache"
                return _CachedJsonResponse(legacy)
            raise RuntimeError(
                "Cache Brave belum tersedia untuk query ini. Jalankan Live Search sekali."
            )

        if self.search_api_calls >= self.max_search_requests_per_run:
            raise RuntimeError(
                f"Hard cap Brave tercapai: {self.search_api_calls}/"
                f"{self.max_search_requests_per_run} network call"
            )

        # Increment before the network call so failed HTTP attempts are still
        # counted against the hard cost cap.
        self.search_api_calls += 1
        response = self.http.get(self.ENDPOINT, params=params, headers=headers)
        payload = response.json()
        self._write_json_cache(cache_key, payload)
        self._working_parameter_mode = mode
        self.parameter_mode = mode
        return _CachedJsonResponse(payload)
