"""KarirLog Search Engine entrypoint.

Usage:
    python main.py collect [--mode live|live_with_fallback|sample|all]
    python main.py check-sources

Outputs (into data/output/):
    discovery_latest.csv
    discovery_YYYYMMDD_HHMMSS.csv
    latest_discovery_diagnostics.json
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT.parent / "karirlog-contracts" / "src"))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from karirlog_search.app import run_collect
from karirlog_search.config import load_json
from karirlog_search.discovery.brave_query_policy import BraveSearchJobSource
from karirlog_search.discovery.http_client import HttpClient
from karirlog_search.logging_setup import setup_logging
from karirlog_search.notifications import send_search_report
from karirlog_search.paths import resolve_path, resolve_settings, resolve_sources_config


def _load(settings_path: str, profile_path: str, mode: str | None):
    settings = load_json(settings_path)
    settings = resolve_settings(settings, _ROOT)
    profile = load_json(profile_path)
    if mode:
        settings["discovery_mode"] = mode
    sources_path = resolve_path(settings.get("sources_config", "config/sources.json"), _ROOT)
    sources = resolve_sources_config(load_json(sources_path), settings)
    return profile, settings, sources


def command_collect(args: argparse.Namespace) -> int:
    profile, settings, sources = _load(args.settings, args.profile, args.mode)
    logger = setup_logging(settings.get("output_dir", "data/output"))
    try:
        stats = run_collect(profile, settings, sources)
    except Exception as exc:
        logger.error("Discovery gagal: %s", exc, exc_info=True)
        print(f"ERROR: discovery gagal: {exc}")
        return 2

    print("\nKARIRLOG SEARCH ENGINE — SELESAI")
    print(f"Mode            : {settings.get('discovery_mode')}")
    print(f"Data mentah     : {stats['raw_found']}")
    print(f"Lowongan unik   : {stats['unique_jobs']}")
    print(f"Duplikat lintas : {stats['cross_source_duplicates']}")
    print(f"Fallback dipakai: {'Ya' if stats['fallback_used'] else 'Tidak'}")
    for item in stats["collectors"]:
        print(f"- {item['status']:8} | {item['found']:3} | {item['name']} | {item['message']}")

    print(f"\nCSV terbaru     : {stats['csv_latest']}")
    print(f"CSV arsip       : {stats['csv_timestamped']}")
    if stats["diagnostics_path"]:
        print(f"Diagnostics     : {stats['diagnostics_path']}")

    telegram_ok, telegram_status = send_search_report(settings, stats)
    print(
        f"Telegram        : {'OK' if telegram_ok else 'INFO'} | {telegram_status}"
    )

    execution_input = (
        _ROOT.parent / "karirlog-execution" / "data" / "input" / "discovery_latest.csv"
    )
    print("\nHANDOFF MANUAL")
    print("1. Buka discovery_latest.csv di Excel.")
    print("2. Review/hapus lowongan yang tidak ingin diteruskan.")
    print(f"3. Simpan/copy hasil review ke: {execution_input}")
    print("4. Baru jalankan KARIRLOG_EXECUTION.bat.")
    print("Search tidak menyalin CSV ke Execution secara otomatis.")
    return 0


def command_check_sources(args: argparse.Namespace) -> int:
    settings = resolve_settings(load_json(args.settings), _ROOT)
    sources_path = resolve_path(settings.get("sources_config", "config/sources.json"), _ROOT)
    sources_config = resolve_sources_config(load_json(sources_path), settings)
    print(f"Discovery mode: {settings.get('discovery_mode', 'live_with_fallback')}\n")
    not_ready = 0
    for source in sources_config.get("sources", []):
        if not isinstance(source, dict):
            continue
        enabled = bool(source.get("enabled", False))
        name = str(source.get("name") or source.get("type") or "Collector")
        collector_type = str(source.get("type", ""))
        status, detail = "DISABLED", "Dinonaktifkan"
        if enabled:
            status, detail = "READY", "Konfigurasi tersedia"
            if collector_type == "brave_search":
                env_name = str(source.get("api_key_env", "BRAVE_SEARCH_API_KEY"))
                if not os.getenv(env_name, "").strip():
                    status, detail = "NEEDS_KEY", f"Isi {env_name} pada .env"
            elif collector_type == "rss" and not source.get("feeds"):
                status, detail = "EMPTY", "Belum ada URL feed"
            elif collector_type in {"url_list", "csv"} and not Path(str(source.get("path", ""))).exists():
                status, detail = "MISSING", f"File tidak ditemukan: {source.get('path', '')}"
        if enabled and status not in {"READY", "NEEDS_KEY"}:
            not_ready += 1
        print(f"- {status:9} | {name} ({collector_type}) | {detail}")
    return 2 if not_ready else 0


def command_show_plan(args: argparse.Namespace) -> int:
    profile, settings, sources = _load(args.settings, args.profile, None)
    print(f"Project root : {_ROOT}")
    print(f"Mode         : {settings.get('discovery_mode', 'live_with_fallback')}")
    print(f"Max jobs     : {settings.get('max_jobs_per_run', 100)}")
    roles = profile.get("target_roles", [])
    locations = profile.get("preferred_locations", [])
    print("Target roles : " + (", ".join(map(str, roles)) if isinstance(roles, list) else "-"))
    print("Locations    : " + (", ".join(map(str, locations)) if isinstance(locations, list) else "-"))
    print("Sources:")

    brave_config: dict | None = None
    for source in sources.get("sources", []):
        if isinstance(source, dict):
            print(
                f"- {'ON' if source.get('enabled') else 'OFF':3} | "
                f"{source.get('type', '-')} | {source.get('name', '-') }"
            )
            if source.get("type") == "brave_search" and source.get("enabled"):
                brave_config = source

    if not brave_config:
        return 0

    planner = BraveSearchJobSource(
        brave_config,
        profile,
        HttpClient(sources.get("http", {})),
        max_jobs=int(settings.get("max_jobs_per_run", 100)),
    )
    queries = planner._queries()
    request_cap = int(brave_config.get("max_search_requests_per_run", len(queries)) or len(queries))
    results_per_query = int(brave_config.get("results_per_query", 20) or 20)

    print("\nBRAVE QUERY PLAN — 0 NETWORK REQUEST")
    print("=" * 72)
    print(f"Planned queries : {len(queries)}")
    print(f"Hard request cap: {request_cap}")
    print(f"Raw ceiling     : sampai {len(queries) * results_per_query} hasil sebelum filter")
    print("Lokasi          : country=ID + validasi setelah search; tidak dijejalkan ke q")
    print()

    plan = planner.executed_query_plan
    if plan:
        for index, item in enumerate(plan, start=1):
            focus = str(item.get("focus", "-"))
            scope = str(item.get("source", "-"))
            print(f"{index:02d}. [{focus}] [{scope}]")
            print(f"    {item.get('query', '')}")
    else:
        for index, query in enumerate(queries, start=1):
            print(f"{index:02d}. {query}")

    print("=" * 72)
    print("Tidak ada request Brave yang dikirim pada menu ini.")
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KarirLog Search Engine")
    sub = parser.add_subparsers(dest="command", required=True)

    collect = sub.add_parser("collect", help="Cari lowongan dan ekspor ke CSV")
    collect.add_argument("--settings", default=str(_ROOT / "config" / "search_settings.json"))
    collect.add_argument("--profile", default=str(_ROOT / "config" / "search_profile.json"))
    collect.add_argument("--mode", choices=["live", "live_with_fallback", "sample", "all"])

    check = sub.add_parser("check-sources", help="Cek kesiapan collector")
    check.add_argument("--settings", default=str(_ROOT / "config" / "search_settings.json"))

    plan = sub.add_parser("show-plan", help="Tampilkan rencana discovery tanpa network")
    plan.add_argument("--settings", default=str(_ROOT / "config" / "search_settings.json"))
    plan.add_argument("--profile", default=str(_ROOT / "config" / "search_profile.json"))
    return parser


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(override=True)
    if os.getenv("REFRESH_SEARCH", "").strip() == "1":
        os.environ["KARIRLOG_BRAVE_REFRESH_SEARCH"] = "1"
    if os.getenv("FORCE_REFRESH", "").strip() == "1":
        os.environ["KARIRLOG_BRAVE_FORCE_REFRESH"] = "1"

    args = make_parser().parse_args()
    if args.command == "collect":
        return command_collect(args)
    if args.command == "check-sources":
        return command_check_sources(args)
    if args.command == "show-plan":
        return command_show_plan(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
