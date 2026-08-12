from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from karirlog_search.discovery.brave_query_policy import BraveSearchJobSource
from karirlog_search.discovery.http_client import HttpClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _source() -> tuple[BraveSearchJobSource, dict, dict]:
    profile = _load_json(PROJECT_ROOT / "config" / "search_profile.json")
    sources = _load_json(PROJECT_ROOT / "config" / "sources.json")
    brave = next(
        item
        for item in sources["sources"]
        if item.get("type") == "brave_search" and item.get("enabled")
    )
    source = BraveSearchJobSource(
        brave,
        profile,
        HttpClient(sources.get("http", {})),
        max_jobs=100,
    )
    return source, profile, brave


def test_high_recall_query_plan_covers_every_configured_target_role() -> None:
    source, profile, brave = _source()
    queries = source._queries()

    assert len(queries) == int(brave["queries_per_run"]) == 12
    combined = "\n".join(queries)
    for role in profile["target_roles"]:
        assert f'"{role}"' in combined, role


def test_focus_configuration_matches_target_roles_without_overlap() -> None:
    _, profile, _ = _source()
    focuses = profile["search_focuses"]

    configured_roles = [role for focus in focuses for role in focus["roles"]]
    assert len(configured_roles) == len(set(configured_roles))
    assert set(configured_roles) == set(profile["target_roles"])
    assert [focus["id"] for focus in focuses] == [
        "CORE_EXPERIENCE",
        "GENERAL_TRANSFERABLE",
    ]
    assert abs(sum(float(focus["weight"]) for focus in focuses) - 1.0) < 1e-9
    assert all("sap" not in role.casefold() for role in configured_roles)


def test_query_budget_is_split_55_45_between_two_focuses() -> None:
    source, _, brave = _source()
    queries = source._queries()

    assert len(queries) == int(brave["queries_per_run"]) == 12
    counts = Counter(str(item.get("focus")) for item in source.executed_query_plan)
    assert counts["CORE_EXPERIENCE"] == 7
    assert counts["GENERAL_TRANSFERABLE"] == 5


def test_location_list_is_not_embedded_in_brave_query() -> None:
    source, profile, brave = _source()
    queries = source._queries()
    combined = "\n".join(queries)

    assert brave["country"] == "ID"
    for location in profile["preferred_locations"]:
        assert f'"{location}"' not in combined


def test_all_queries_are_broad_and_sources_are_post_filtered() -> None:
    source, _, _ = _source()
    queries = source._queries()

    assert len(source.executed_query_plan) == len(queries) == 12
    assert source.query_source_groups == {}
    assert all(
        item["source"] == "Broad web -> post-filter sources"
        for item in source.executed_query_plan
    )
    assert all("site:" not in query.casefold() for query in queries)


def test_generated_queries_respect_brave_limits() -> None:
    source, _, _ = _source()
    queries = source._queries()

    for item, query in zip(source.executed_query_plan, queries):
        assert item["focus"] in {"CORE_EXPERIENCE", "GENERAL_TRANSFERABLE"}
        assert item["focus_label"]
        assert len(query) <= 400
        assert len(query.split()) <= 50


def test_failed_brave_attempts_are_counted_before_network_call() -> None:
    policy_source = (
        PROJECT_ROOT
        / "src"
        / "karirlog_search"
        / "discovery"
        / "brave_query_policy.py"
    ).read_text(encoding="utf-8")

    assert "Hard cap Brave tercapai" in policy_source
    increment = policy_source.index("self.search_api_calls += 1")
    network = policy_source.index("response = self.http.get", increment)
    assert increment < network
