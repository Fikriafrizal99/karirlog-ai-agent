from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

import requests


TELEGRAM_MESSAGE_LIMIT = 3800


def build_summary(stats: dict[str, Any]) -> str:
    failed = sum(
        1 for item in stats.get("collectors", []) if item.get("status") == "FAILED"
    )
    skipped = sum(
        1 for item in stats.get("collectors", []) if item.get("status") == "SKIPPED"
    )
    fallback = "Ya" if stats.get("fallback_used") else "Tidak"
    return (
        "🤖 KARIRLOG AI AGENT V1.0\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"Discovery          : {stats.get('discovery_mode', '-')}\n"
        f"Analysis           : {stats.get('analysis_mode', '-')}\n"
        f"Data mentah        : {stats.get('raw_found', 0)}\n"
        f"Lowongan unik      : {stats.get('total_found', 0)}\n"
        f"Lowongan baru      : {stats.get('new_jobs', 0)}\n"
        f"Dianalisis ulang   : {stats.get('reanalyzed_jobs', 0)}\n"
        f"Analisis dipakai   : {stats.get('reused_analyses', 0)}\n"
        f"Duplikat histori   : {stats.get('duplicates', 0)}\n"
        f"Duplikat lintas src: {stats.get('cross_source_duplicates', 0)}\n"
        f"Fallback CSV       : {fallback}\n"
        f"Collector gagal    : {failed} | dilewati: {skipped}\n"
        f"🧠 AI              : {stats.get('ai_analyzed', 0)}\n"
        f"📐 Rule            : {stats.get('rule_analyzed', 0)}\n"
        f"↩️ AI fallback     : {stats.get('ai_fallbacks', 0)}\n"
        f"⚠️ Analysis error  : {stats.get('analysis_failures', 0)}\n"
        f"✅ APPLY           : {stats.get('apply_count', 0)}\n"
        f"🟡 REVIEW          : {stats.get('review_count', 0)}\n"
        f"⛔ SKIP            : {stats.get('skip_count', 0)}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Draft siap      : {stats.get('application_ready', 0)}\n"
        f"✉️ Email ready     : {stats.get('email_ready', 0)}\n"
        f"🌐 Portal ready    : {stats.get('portal_ready', 0)}\n"
        f"🟡 Review CV       : {stats.get('application_review_cv', 0)}\n"
        f"⛔ Paket diblokir  : {stats.get('application_blocked', 0)}\n"
        f"📄 CV missing      : {stats.get('cv_missing', 0)}\n"
        f"🔄 Paket dibangun  : {stats.get('application_rebuilds', 0)}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"Apply mode: {stats.get('auto_apply_mode', 'draft_only')}"
    )


def split_telegram_message(
    message: str, max_length: int = TELEGRAM_MESSAGE_LIMIT
) -> list[str]:
    """Split a long Telegram message on line boundaries."""
    text = str(message or "").strip()
    if not text:
        return [""]
    if len(text) <= max_length:
        return [text]

    parts: list[str] = []
    current: list[str] = []
    current_length = 0
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        addition = len(line) + (1 if current else 0)
        if current and current_length + addition > max_length:
            parts.append("\n".join(current).strip())
            current = []
            current_length = 0
        while len(line) > max_length:
            if current:
                parts.append("\n".join(current).strip())
                current = []
                current_length = 0
            parts.append(line[:max_length])
            line = line[max_length:]
        current.append(line)
        current_length += len(line) + (1 if len(current) > 1 else 0)
    if current:
        parts.append("\n".join(current).strip())
    return [part for part in parts if part]


def send_telegram(settings: dict[str, Any], message: str) -> tuple[bool, str]:
    if not settings.get("telegram_enabled", False):
        return False, "Telegram dinonaktifkan"

    token = os.getenv(str(settings.get("telegram_bot_token_env", "TELEGRAM_BOT_TOKEN")), "")
    chat_id = os.getenv(str(settings.get("telegram_chat_id_env", "TELEGRAM_CHAT_ID")), "")
    if not token or not chat_id:
        return False, "Token atau chat ID Telegram belum diisi"

    parts = split_telegram_message(message)
    try:
        for part in parts:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": part},
                timeout=20,
            )
            response.raise_for_status()
        suffix = f" ({len(parts)} bagian)" if len(parts) > 1 else ""
        return True, f"Telegram terkirim{suffix}"
    except requests.RequestException as exc:
        return False, f"Telegram gagal: {exc}"


def build_delivery_summary(result: dict[str, Any]) -> str:
    return (
        "✉️ KARIRLOG DELIVERY UPDATE\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"Gmail draft dibuat : {result.get('created', 0)}\n"
        f"Gagal              : {result.get('failed', 0)}\n"
        f"Dilewati           : {result.get('skipped', 0)}"
    )


def build_portal_queue_summary(result: dict[str, Any]) -> str:
    return (
        "🌐 KARIRLOG PORTAL QUEUE\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"Antrean    : {result.get('queued', 0)}\n"
        f"Diproses   : {result.get('processed', 0)}\n"
        f"Submitted  : {result.get('submitted', 0)}\n"
        f"Review     : {result.get('review', 0)}\n"
        f"Dilewati   : {result.get('skipped', 0)}\n"
        f"Gagal      : {result.get('failed', 0)}"
    )


def build_application_report(rows: Iterable[Mapping[str, Any]]) -> str:
    """Build a human-readable report of where applications have been sent."""
    items = [dict(row) for row in rows]
    counts = Counter(str(item.get("status") or "UNKNOWN") for item in items)

    submitted_statuses = {"PORTAL_SUBMITTED", "EMAIL_SENT"}
    pending_statuses = {
        "DRAFT_READY_PORTAL",
        "PORTAL_REVIEW_REQUIRED",
        "DRAFT_READY_EMAIL",
        "GMAIL_DRAFT_CREATED",
        "EMAIL_APPROVAL_PENDING",
    }
    failed_statuses = {
        "PORTAL_ASSIST_FAILED",
        "GMAIL_DRAFT_FAILED",
        "BLOCKED_CV_MISSING",
        "BLOCKED_DESTINATION",
        "REVIEW_CV",
    }

    submitted = [item for item in items if str(item.get("status")) in submitted_statuses]
    pending = [item for item in items if str(item.get("status")) in pending_statuses]
    failed = [item for item in items if str(item.get("status")) in failed_statuses]
    other = [
        item
        for item in items
        if item not in submitted and item not in pending and item not in failed
    ]

    lines = [
        "📋 KARIRLOG APPLICATION REPORT",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Total tercatat      : {len(items)}",
        f"✅ Sudah dikirim    : {len(submitted)}",
        f"🟡 Perlu dilanjutkan: {len(pending)}",
        f"🔴 Gagal/terblokir  : {len(failed)}",
        f"⚪ Status lain      : {len(other)}",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    def add_section(title: str, section_items: list[dict[str, Any]]) -> None:
        if not section_items:
            return
        lines.extend(["", title])
        for item in section_items:
            app_id = int(item.get("id") or 0)
            status = str(item.get("status") or "-")
            lifecycle_state = str(item.get("lifecycle_state") or "-")
            channel = str(item.get("apply_channel") or "-")
            company = str(item.get("company") or "-").strip()
            position = str(item.get("title") or "-").strip()
            lines.append(f"Lifecycle: {lifecycle_state}")
            lines.append(
                f"#{app_id:03} | {channel} | {status}\n{company} — {position}"
            )

    add_section("✅ SUDAH DIKIRIM", submitted)
    add_section("🟡 PERLU DILANJUTKAN", pending)
    add_section("🔴 GAGAL / TERBLOKIR", failed)
    add_section("⚪ STATUS LAIN", other)

    if counts:
        lines.extend(["", "Rincian status:"])
        for status, total in sorted(counts.items()):
            lines.append(f"• {status}: {total}")
    return "\n".join(lines).strip()
