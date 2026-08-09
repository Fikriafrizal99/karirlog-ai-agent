from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests


def build_search_summary(stats: dict[str, Any]) -> str:
    collectors = stats.get("collectors", []) or []
    failed = sum(1 for item in collectors if item.get("status") == "FAILED")
    skipped = sum(1 for item in collectors if item.get("status") == "SKIPPED")
    fallback = "Ya" if stats.get("fallback_used") else "Tidak"

    lines = [
        "🔎 KARIRLOG SEARCH — SELESAI",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Data mentah      : {stats.get('raw_found', 0)}",
        f"Lowongan unik    : {stats.get('unique_jobs', 0)}",
        f"Duplikat lintas  : {stats.get('cross_source_duplicates', 0)}",
        f"Fallback CSV     : {fallback}",
        f"Collector gagal  : {failed}",
        f"Collector skip   : {skipped}",
        "━━━━━━━━━━━━━━━━━━━━",
        "📄 CSV siap direview di Excel.",
        "Execution tidak dijalankan otomatis.",
    ]
    return "\n".join(lines)


def _credentials(settings: dict[str, Any]) -> tuple[str, str]:
    token_env = str(settings.get("telegram_bot_token_env", "TELEGRAM_BOT_TOKEN"))
    chat_env = str(settings.get("telegram_chat_id_env", "TELEGRAM_CHAT_ID"))
    return os.getenv(token_env, "").strip(), os.getenv(chat_env, "").strip()


def send_search_report(
    settings: dict[str, Any],
    stats: dict[str, Any],
) -> tuple[bool, str]:
    """Send Search summary and discovery_latest.csv to Telegram.

    Telegram is notification-only. A Telegram failure never removes or changes
    the CSV handoff produced by Search.
    """
    if not settings.get("telegram_enabled", False):
        return False, "dinonaktifkan"

    token, chat_id = _credentials(settings)
    if not token or not chat_id:
        return False, "token/chat ID belum diisi"

    timeout = max(5, int(settings.get("telegram_timeout_seconds", 20)))
    base_url = f"https://api.telegram.org/bot{token}"

    try:
        summary_response = requests.post(
            f"{base_url}/sendMessage",
            json={"chat_id": chat_id, "text": build_search_summary(stats)},
            timeout=timeout,
        )
        summary_response.raise_for_status()

        if not settings.get("telegram_send_csv", True):
            return True, "report terkirim; pengiriman CSV dinonaktifkan"

        csv_path = Path(str(stats.get("csv_latest", "")))
        if not csv_path.is_file():
            return True, f"report terkirim; CSV tidak ditemukan: {csv_path}"

        caption = (
            "📎 KARIRLOG SEARCH CSV\n"
            f"Lowongan unik: {stats.get('unique_jobs', 0)}\n"
            "Review file ini di Excel sebelum diteruskan ke Execution."
        )
        with csv_path.open("rb") as handle:
            document_response = requests.post(
                f"{base_url}/sendDocument",
                data={"chat_id": chat_id, "caption": caption},
                files={
                    "document": (
                        "discovery_latest.csv",
                        handle,
                        "text/csv",
                    )
                },
                timeout=timeout,
            )
            document_response.raise_for_status()

        return True, "report + discovery_latest.csv terkirim"
    except requests.RequestException as exc:
        return False, f"gagal: {exc}"
