from __future__ import annotations

import argparse
import getpass
import json
import math
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEARCH_ROOT = ROOT / "karirlog-search"
EXEC_ROOT = ROOT / "karirlog-execution"

PRICING_AS_OF = "2026-08-09"
BRAVE_USD_PER_1000_REQUESTS = 5.0
BRAVE_MONTHLY_CREDIT_USD = 5.0
OPENAI_PRICING = {
    "gpt-5-mini": {
        "input_per_million": 0.25,
        "cached_input_per_million": 0.025,
        "output_per_million": 2.0,
    }
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return values
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def _env_value(name: str) -> str:
    direct = os.getenv(name, "").strip()
    if direct:
        return direct
    for path in (EXEC_ROOT / ".env", SEARCH_ROOT / ".env"):
        value = _load_env_file(path).get(name, "").strip()
        if value:
            return value
    return ""


def _ready(value: str) -> str:
    return "READY" if value.strip() else "MISSING"


def _file_status(path: Path) -> str:
    return "READY" if path.is_file() else "MISSING"


def _dir_status(path: Path) -> str:
    return "READY" if path.is_dir() else "MISSING"


def command_status() -> int:
    print("KARIRLOG SYSTEM STATUS")
    print("=" * 58)
    print(f"Search venv       : {_file_status(SEARCH_ROOT / '.venv' / 'Scripts' / 'python.exe')}")
    print(f"Execution venv    : {_file_status(EXEC_ROOT / '.venv' / 'Scripts' / 'python.exe')}")
    print(f"Brave API         : {_ready(_env_value('BRAVE_SEARCH_API_KEY'))}")
    print(f"OpenAI API        : {_ready(_env_value('OPENAI_API_KEY'))}")
    print(f"Telegram Bot      : {_ready(_env_value('TELEGRAM_BOT_TOKEN'))}")
    print(f"Telegram Chat ID  : {_ready(_env_value('TELEGRAM_CHAT_ID'))}")
    print(f"Gmail credentials : {_file_status(EXEC_ROOT / 'credentials.json')}")
    print(f"Gmail token       : {_file_status(EXEC_ROOT / 'data' / 'secrets' / 'gmail_token.json')}")
    print(f"Candidate profile : {_file_status(EXEC_ROOT / 'config' / 'candidate_profile.json')}")
    print(f"Execution input   : {_file_status(EXEC_ROOT / 'data' / 'input' / 'discovery_latest.csv')}")
    print(f"Search output     : {_file_status(SEARCH_ROOT / 'data' / 'output' / 'discovery_latest.csv')}")
    print(f"Database          : {_file_status(EXEC_ROOT / 'data' / 'database' / 'karirlog.db')}")
    print(f"CV folder         : {_dir_status(EXEC_ROOT / 'documents' / 'cv')}")
    print("=" * 58)
    print("Credential hanya ditampilkan sebagai READY/MISSING; nilai rahasia tidak dicetak.")
    return 0


def _write_env_values(path: Path, updates: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines: list[str] = []
    if path.is_file():
        try:
            existing_lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            existing_lines = []

    remaining = dict(updates)
    output: list[str] = []
    for raw_line in existing_lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            output.append(raw_line)
            continue
        key = raw_line.split("=", 1)[0].strip()
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(raw_line)

    if output and output[-1].strip():
        output.append("")
    for key, value in remaining.items():
        output.append(f"{key}={value}")
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def command_telegram_config() -> int:
    search_env = _load_env_file(SEARCH_ROOT / ".env")
    exec_env = _load_env_file(EXEC_ROOT / ".env")
    current_token = (
        exec_env.get("TELEGRAM_BOT_TOKEN", "").strip()
        or search_env.get("TELEGRAM_BOT_TOKEN", "").strip()
    )
    current_chat = (
        exec_env.get("TELEGRAM_CHAT_ID", "").strip()
        or search_env.get("TELEGRAM_CHAT_ID", "").strip()
    )

    print("SET / SYNC TELEGRAM")
    print("=" * 42)
    print("Token tidak akan ditampilkan.")
    token = getpass.getpass(
        "Telegram Bot Token (Enter = pertahankan yang ada): "
    ).strip()
    chat_id = input(
        "Telegram Chat ID (Enter = pertahankan yang ada): "
    ).strip()
    token = token or current_token
    chat_id = chat_id or current_chat
    if not token or not chat_id:
        print("ERROR: token dan chat ID wajib tersedia.")
        return 2

    updates = {
        "TELEGRAM_BOT_TOKEN": token,
        "TELEGRAM_CHAT_ID": chat_id,
    }
    _write_env_values(SEARCH_ROOT / ".env", updates)
    _write_env_values(EXEC_ROOT / ".env", updates)
    print("Telegram settings tersimpan dan disinkronkan ke Search + Execution.")
    print("Gunakan menu Telegram Test untuk memastikan bot dapat mengirim pesan.")
    return 0


def _telegram_credentials() -> tuple[str, str]:
    return _env_value("TELEGRAM_BOT_TOKEN"), _env_value("TELEGRAM_CHAT_ID")


def command_telegram_status() -> int:
    token, chat_id = _telegram_credentials()
    print("TELEGRAM STATUS")
    print("=" * 42)
    print(f"BOT TOKEN : {_ready(token)}")
    print(f"CHAT ID   : {_ready(chat_id)}")
    print(f"Search env: {_file_status(SEARCH_ROOT / '.env')}")
    print(f"Exec env  : {_file_status(EXEC_ROOT / '.env')}")
    if token and chat_id:
        print("STATUS    : CONFIGURED")
        return 0
    print("STATUS    : BELUM LENGKAP")
    return 2


def command_telegram_test() -> int:
    token, chat_id = _telegram_credentials()
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum tersedia.")
        return 2
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": (
                "✅ KARIRLOG TELEGRAM TEST\n"
                "Koneksi Telegram siap dipakai untuk Search dan Execution."
            ),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            ok = 200 <= int(response.status) < 300
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Telegram test gagal: {exc}")
        return 2
    print("Telegram test terkirim." if ok else "Telegram test gagal.")
    return 0 if ok else 2


def _brave_config() -> dict[str, Any]:
    sources = _load_json(SEARCH_ROOT / "config" / "sources.json").get("sources", [])
    if not isinstance(sources, list):
        return {}
    for item in sources:
        if isinstance(item, dict) and item.get("type") == "brave_search":
            return item
    return {}


def _latest_brave_calls() -> int | None:
    path = SEARCH_ROOT / "data" / "output" / "latest_discovery_diagnostics.json"
    data = _load_json(path)
    search = data.get("search", {})
    if isinstance(search, dict) and isinstance(search.get("api_calls"), int):
        return int(search["api_calls"])
    return None


def _money(value: float) -> str:
    return f"${value:.4f}"


def command_api_audit(jobs: int) -> int:
    brave = _brave_config()
    execution = _load_json(EXEC_ROOT / "config" / "execution_settings.json")

    queries = max(1, int(brave.get("queries_per_run", 1) or 1))
    request_cap = max(1, int(brave.get("max_search_requests_per_run", queries) or queries))
    pages = max(1, int(brave.get("search_pages_per_query", 1) or 1))
    planned_brave_requests = min(request_cap, queries * pages)
    brave_run_cost = planned_brave_requests * BRAVE_USD_PER_1000_REQUESTS / 1000
    monthly_full_runs_from_credit = math.floor(
        BRAVE_MONTHLY_CREDIT_USD / brave_run_cost
    ) if brave_run_cost else 0

    model = str(execution.get("ai_model", "gpt-5-mini"))
    price = OPENAI_PRICING.get(model)
    max_description_chars = max(1000, int(execution.get("ai_max_description_chars", 8000) or 8000))
    max_output = max(1, int(execution.get("ai_max_output_tokens", 1800) or 1800))
    reasoning = str(execution.get("ai_reasoning_effort", "minimal"))
    jobs = max(1, int(jobs))

    estimated_input_per_job = math.ceil((max_description_chars + 5000) / 4)
    typical_output_per_job = min(700, max_output)

    print("KARIRLOG API USAGE / COST AUDIT")
    print("=" * 64)
    print(f"Pricing reference : {PRICING_AS_OF} (ubah jika provider mengubah harga)")
    print()
    print("BRAVE SEARCH")
    print(f"Planned query/run : {queries}")
    print(f"Pages/query       : {pages}")
    print(f"Request cap/run   : {request_cap}")
    print(f"Max normal/run    : {planned_brave_requests} request")
    print(f"Cache only        : 0 request Brave")
    print(f"Detail hydration  : HTTP ke halaman lowongan, bukan Brave Search API")
    actual = _latest_brave_calls()
    if actual is not None:
        print(f"Last diagnostics  : {actual} Brave API call")
    print(f"List price/run    : {_money(brave_run_cost)}")
    print(
        f"$5 monthly credit : sekitar {monthly_full_runs_from_credit} full live run/bulan "
        f"pada {planned_brave_requests} request/run"
    )
    print()
    print("OPENAI")
    print(f"Mode              : {execution.get('analysis_mode', '-')}")
    print(f"Model             : {model}")
    print(f"Reasoning effort  : {reasoning}")
    print(f"Description cap   : {max_description_chars:,} karakter/job")
    print(f"Output cap        : {max_output:,} token/job")
    print(f"Job estimate      : {jobs}")
    if price:
        typical_input = jobs * estimated_input_per_job
        typical_output = jobs * typical_output_per_job
        typical_cost = (
            typical_input * price["input_per_million"] / 1_000_000
            + typical_output * price["output_per_million"] / 1_000_000
        )
        output_cap_cost = (
            typical_input * price["input_per_million"] / 1_000_000
            + jobs * max_output * price["output_per_million"] / 1_000_000
        )
        print(f"Input planning    : ~{estimated_input_per_job:,} token/job")
        print(f"Typical output    : ~{typical_output_per_job:,} token/job")
        print(f"Typical estimate  : {_money(typical_cost)} / {jobs} job")
        print(f"Configured ceiling: ~{_money(output_cap_cost)} / {jobs} job")
        print(
            "Catatan           : biaya aktual bisa lebih rendah karena output biasanya "
            "di bawah cap dan cached input GPT-5 mini lebih murah."
        )
    else:
        print("Estimasi biaya    : pricing model belum ada di helper; cek dashboard provider.")
    print()
    print("REKOMENDASI")
    print("- 1-2 Live Search/hari: hemat; gunakan Cache Only saat testing.")
    print("- Jangan Full Refresh berulang kecuali detail halaman memang stale/bermasalah.")
    print("- AI tetap dianalisis per job baru/reanalysis; job lama dapat direuse oleh Execution.")
    print("- GPT-5 mini dipertahankan karena sangat murah untuk job-fit terstruktur.")
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KarirLog control/status helper")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("telegram-status")
    sub.add_parser("telegram-config")
    sub.add_parser("telegram-test")
    audit = sub.add_parser("api-audit")
    audit.add_argument("--jobs", type=int, default=30)
    return parser


def main() -> int:
    args = make_parser().parse_args()
    if args.command == "status":
        return command_status()
    if args.command == "telegram-status":
        return command_telegram_status()
    if args.command == "telegram-config":
        return command_telegram_config()
    if args.command == "telegram-test":
        return command_telegram_test()
    if args.command == "api-audit":
        return command_api_audit(args.jobs)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
