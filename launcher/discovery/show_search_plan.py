from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from karirlog.discovery.brave_source import BraveSearchJobSource  # noqa: E402


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    sources_path = ROOT / "config" / "sources.json"
    profile_path = ROOT / "config" / "profil.json"
    if not profile_path.exists():
        profile_path = ROOT / "config" / "profile.json"
    if not sources_path.exists() or not profile_path.exists():
        print("ERROR: config/sources.json atau config/profile.json tidak ditemukan.")
        return 2
    sources_payload = load_json(sources_path)
    profile = load_json(profile_path)
    brave = next((item for item in sources_payload.get("sources", []) if isinstance(item, dict) and item.get("type") == "brave_search"), None)
    if brave is None:
        print("ERROR: collector brave_search tidak ditemukan.")
        return 2
    source = BraveSearchJobSource(brave, profile, object(), max_jobs=100)
    source._queries()
    print("\n=== RENCANA PENCARIAN - TANPA MEMANGGIL BRAVE API ===\n")
    print(f"Total query maksimum : {len(source.executed_query_plan)}")
    print(f"Request API maksimum : {brave.get('max_search_requests_per_run', len(source.executed_query_plan))}")
    print(f"Mode parameter       : {brave.get('brave_parameter_mode', 'otomatis')}")
    print()
    for index, item in enumerate(source.executed_query_plan, start=1):
        print(f"[{index:02d}] {item['source']} - kelompok {item['family']}")
        print(f"     {item['query']}")
    print("\nPerintah ini hanya menampilkan query dan memakai 0 request Brave.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
