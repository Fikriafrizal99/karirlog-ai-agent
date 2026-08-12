from __future__ import annotations

from pathlib import Path

from karirlog_search.notifications import build_search_summary, send_search_report


class _Response:
    def raise_for_status(self) -> None:
        return None


def test_build_search_summary() -> None:
    text = build_search_summary(
        {
            "raw_found": 12,
            "unique_jobs": 8,
            "cross_source_duplicates": 4,
            "fallback_used": False,
            "collectors": [
                {"status": "SUCCESS"},
                {"status": "SKIPPED"},
                {"status": "FAILED"},
            ],
        }
    )
    assert "Data mentah      : 12" in text
    assert "Lowongan unik    : 8" in text
    assert "Collector gagal  : 1" in text
    assert "Collector skip   : 1" in text


def test_send_search_report_sends_message_and_csv(
    tmp_path: Path, monkeypatch
) -> None:
    csv_path = tmp_path / "discovery_latest.csv"
    csv_path.write_text("title,company,url\nRole,Company,https://example.test\n", encoding="utf-8")

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456")

    calls: list[dict[str, object]] = []

    def fake_post(url: str, **kwargs: object) -> _Response:
        calls.append({"url": url, **kwargs})
        return _Response()

    monkeypatch.setattr("karirlog_search.notifications.requests.post", fake_post)

    ok, status = send_search_report(
        {
            "telegram_enabled": True,
            "telegram_send_csv": True,
            "telegram_bot_token_env": "TELEGRAM_BOT_TOKEN",
            "telegram_chat_id_env": "TELEGRAM_CHAT_ID",
            "telegram_timeout_seconds": 20,
        },
        {
            "raw_found": 5,
            "unique_jobs": 3,
            "cross_source_duplicates": 2,
            "fallback_used": False,
            "collectors": [],
            "csv_latest": str(csv_path),
        },
    )

    assert ok is True
    assert "discovery_latest.csv terkirim" in status
    assert len(calls) == 2
    assert str(calls[0]["url"]).endswith("/sendMessage")
    assert str(calls[1]["url"]).endswith("/sendDocument")

    document_call = calls[1]
    data = document_call["data"]
    files = document_call["files"]
    assert isinstance(data, dict)
    assert data["chat_id"] == "123456"
    assert isinstance(files, dict)
    assert files["document"][0] == "discovery_latest.csv"


def test_missing_telegram_credentials_does_not_fail_search(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    ok, status = send_search_report(
        {"telegram_enabled": True},
        {"csv_latest": str(tmp_path / "discovery_latest.csv")},
    )

    assert ok is False
    assert "belum diisi" in status
