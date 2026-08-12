from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .models import AnalysisResult, ApplicationPackageResult, Job
from .lifecycle import lifecycle_for_status


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    url TEXT,
    description TEXT,
    source TEXT,
    apply_email TEXT,
    posted_at TEXT,
    source_job_id TEXT,
    employment_type TEXT,
    salary TEXT,
    remote INTEGER NOT NULL DEFAULT 0,
    discovered_at TEXT NOT NULL DEFAULT '',
    discovery_run_id TEXT NOT NULL DEFAULT '',
    lifecycle_state TEXT NOT NULL DEFAULT 'NEW',
    lifecycle_updated_at TEXT,
    lifecycle_reason TEXT NOT NULL DEFAULT '',
    analysis_config_fingerprint TEXT NOT NULL DEFAULT '',
    package_config_fingerprint TEXT NOT NULL DEFAULT '',
    last_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    score INTEGER NOT NULL,
    decision TEXT NOT NULL,
    analysis_mode TEXT NOT NULL DEFAULT 'RULE_ONLY',
    provider TEXT NOT NULL DEFAULT 'local',
    model TEXT NOT NULL DEFAULT '',
    confidence INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT '',
    seniority_level TEXT NOT NULL DEFAULT 'UNKNOWN',
    estimated_years_required INTEGER NOT NULL DEFAULT 0,
    matched_roles TEXT NOT NULL DEFAULT '[]',
    required_requirements TEXT NOT NULL DEFAULT '[]',
    preferred_requirements TEXT NOT NULL DEFAULT '[]',
    matched_required TEXT NOT NULL DEFAULT '[]',
    missing_required TEXT NOT NULL DEFAULT '[]',
    matched_skills TEXT NOT NULL DEFAULT '[]',
    missing_skills TEXT NOT NULL DEFAULT '[]',
    transferable_strengths TEXT NOT NULL DEFAULT '[]',
    red_flags TEXT NOT NULL DEFAULT '[]',
    reasons TEXT NOT NULL DEFAULT '[]',
    config_fingerprint TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    mode TEXT NOT NULL,
    output_path TEXT,
    selected_cv_id TEXT NOT NULL DEFAULT '',
    selected_cv_path TEXT NOT NULL DEFAULT '',
    cv_selection_status TEXT NOT NULL DEFAULT '',
    cv_selection_score INTEGER NOT NULL DEFAULT 0,
    apply_channel TEXT NOT NULL DEFAULT '',
    recipient TEXT NOT NULL DEFAULT '',
    manifest_path TEXT NOT NULL DEFAULT '',
    package_config_fingerprint TEXT NOT NULL DEFAULT '',
    gmail_draft_id TEXT NOT NULL DEFAULT '',
    gmail_message_id TEXT NOT NULL DEFAULT '',
    approval_code_hash TEXT NOT NULL DEFAULT '',
    approved_at TEXT,
    sent_at TEXT,
    portal_report_path TEXT NOT NULL DEFAULT '',
    last_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    total_found INTEGER NOT NULL DEFAULT 0,
    raw_found INTEGER NOT NULL DEFAULT 0,
    new_jobs INTEGER NOT NULL DEFAULT 0,
    reanalyzed_jobs INTEGER NOT NULL DEFAULT 0,
    duplicates INTEGER NOT NULL DEFAULT 0,
    cross_source_duplicates INTEGER NOT NULL DEFAULT 0,
    apply_count INTEGER NOT NULL DEFAULT 0,
    review_count INTEGER NOT NULL DEFAULT 0,
    skip_count INTEGER NOT NULL DEFAULT 0,
    fallback_used INTEGER NOT NULL DEFAULT 0,
    ai_analyzed INTEGER NOT NULL DEFAULT 0,
    rule_analyzed INTEGER NOT NULL DEFAULT 0,
    ai_fallbacks INTEGER NOT NULL DEFAULT 0,
    analysis_failures INTEGER NOT NULL DEFAULT 0,
    application_ready INTEGER NOT NULL DEFAULT 0,
    application_review_cv INTEGER NOT NULL DEFAULT 0,
    application_blocked INTEGER NOT NULL DEFAULT 0,
    email_ready INTEGER NOT NULL DEFAULT 0,
    portal_ready INTEGER NOT NULL DEFAULT 0,
    cv_missing INTEGER NOT NULL DEFAULT 0,
    application_rebuilds INTEGER NOT NULL DEFAULT 0,
    reused_analyses INTEGER NOT NULL DEFAULT 0,
    report_path TEXT
);

CREATE TABLE IF NOT EXISTS collector_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    collector_type TEXT NOT NULL,
    status TEXT NOT NULL,
    found INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS application_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER,
    job_id INTEGER,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(application_id) REFERENCES applications(id),
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self._migrate_legacy_schema()
        self.connection.commit()

    def _table_columns(self, table: str) -> set[str]:
        return {
            str(row["name"])
            for row in self.connection.execute(f"PRAGMA table_info({table})").fetchall()
        }

    def _ensure_column(self, table: str, name: str, definition: str) -> None:
        if name not in self._table_columns(table):
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def _migrate_legacy_schema(self) -> None:
        for name, definition in (
            ("source_job_id", "TEXT"),
            ("employment_type", "TEXT"),
            ("salary", "TEXT"),
            ("remote", "INTEGER NOT NULL DEFAULT 0"),
            ("discovered_at", "TEXT NOT NULL DEFAULT ''"),
            ("discovery_run_id", "TEXT NOT NULL DEFAULT ''"),
            ("lifecycle_state", "TEXT NOT NULL DEFAULT 'NEW'"),
            ("lifecycle_updated_at", "TEXT"),
            ("lifecycle_reason", "TEXT NOT NULL DEFAULT ''"),
            ("analysis_config_fingerprint", "TEXT NOT NULL DEFAULT ''"),
            ("package_config_fingerprint", "TEXT NOT NULL DEFAULT ''"),
            ("last_error", "TEXT NOT NULL DEFAULT ''"),
        ):
            self._ensure_column("jobs", name, definition)

        for name, definition in (
            ("analysis_mode", "TEXT NOT NULL DEFAULT 'RULE_ONLY'"),
            ("provider", "TEXT NOT NULL DEFAULT 'local'"),
            ("model", "TEXT NOT NULL DEFAULT ''"),
            ("confidence", "INTEGER NOT NULL DEFAULT 0"),
            ("summary", "TEXT NOT NULL DEFAULT ''"),
            ("seniority_level", "TEXT NOT NULL DEFAULT 'UNKNOWN'"),
            ("estimated_years_required", "INTEGER NOT NULL DEFAULT 0"),
            ("required_requirements", "TEXT NOT NULL DEFAULT '[]'"),
            ("preferred_requirements", "TEXT NOT NULL DEFAULT '[]'"),
            ("matched_required", "TEXT NOT NULL DEFAULT '[]'"),
            ("missing_required", "TEXT NOT NULL DEFAULT '[]'"),
            ("transferable_strengths", "TEXT NOT NULL DEFAULT '[]'"),
            ("red_flags", "TEXT NOT NULL DEFAULT '[]'"),
            ("config_fingerprint", "TEXT NOT NULL DEFAULT ''"),
        ):
            self._ensure_column("analyses", name, definition)

        for name, definition in (
            ("selected_cv_id", "TEXT NOT NULL DEFAULT ''"),
            ("selected_cv_path", "TEXT NOT NULL DEFAULT ''"),
            ("cv_selection_status", "TEXT NOT NULL DEFAULT ''"),
            ("cv_selection_score", "INTEGER NOT NULL DEFAULT 0"),
            ("apply_channel", "TEXT NOT NULL DEFAULT ''"),
            ("recipient", "TEXT NOT NULL DEFAULT ''"),
            ("manifest_path", "TEXT NOT NULL DEFAULT ''"),
            ("package_config_fingerprint", "TEXT NOT NULL DEFAULT ''"),
            ("gmail_draft_id", "TEXT NOT NULL DEFAULT ''"),
            ("gmail_message_id", "TEXT NOT NULL DEFAULT ''"),
            ("approval_code_hash", "TEXT NOT NULL DEFAULT ''"),
            ("approved_at", "TEXT"),
            ("sent_at", "TEXT"),
            ("portal_report_path", "TEXT NOT NULL DEFAULT ''"),
            ("last_error", "TEXT NOT NULL DEFAULT ''"),
            ("updated_at", "TEXT"),
            # Execution Engine lifecycle layer (additive; never replaces `status`
            # so the legacy delivery flow keeps reading the same values).
            ("lifecycle_state", "TEXT NOT NULL DEFAULT 'NEW'"),
        ):
            self._ensure_column("applications", name, definition)

        for name, definition in (
            ("raw_found", "INTEGER NOT NULL DEFAULT 0"),
            ("reanalyzed_jobs", "INTEGER NOT NULL DEFAULT 0"),
            ("cross_source_duplicates", "INTEGER NOT NULL DEFAULT 0"),
            ("fallback_used", "INTEGER NOT NULL DEFAULT 0"),
            ("ai_analyzed", "INTEGER NOT NULL DEFAULT 0"),
            ("rule_analyzed", "INTEGER NOT NULL DEFAULT 0"),
            ("ai_fallbacks", "INTEGER NOT NULL DEFAULT 0"),
            ("analysis_failures", "INTEGER NOT NULL DEFAULT 0"),
            ("application_ready", "INTEGER NOT NULL DEFAULT 0"),
            ("application_review_cv", "INTEGER NOT NULL DEFAULT 0"),
            ("application_blocked", "INTEGER NOT NULL DEFAULT 0"),
            ("email_ready", "INTEGER NOT NULL DEFAULT 0"),
            ("portal_ready", "INTEGER NOT NULL DEFAULT 0"),
            ("cv_missing", "INTEGER NOT NULL DEFAULT 0"),
            ("application_rebuilds", "INTEGER NOT NULL DEFAULT 0"),
            ("reused_analyses", "INTEGER NOT NULL DEFAULT 0"),
        ):
            self._ensure_column("runs", name, definition)

    def close(self) -> None:
        self.connection.close()

    def insert_job(self, job: Job) -> tuple[int, bool]:
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO jobs
            (fingerprint, title, company, location, url, description, source,
             apply_email, posted_at, source_job_id, employment_type, salary, remote,
             discovered_at, discovery_run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.fingerprint,
                job.title,
                job.company,
                job.location,
                job.url,
                job.description,
                job.source,
                job.apply_email,
                job.posted_at,
                job.source_job_id,
                job.employment_type,
                job.salary,
                int(job.remote),
                job.discovered_at,
                job.discovery_run_id,
            ),
        )
        self.connection.commit()
        if cursor.rowcount == 1:
            return int(cursor.lastrowid), True
        row = self.connection.execute(
            "SELECT id FROM jobs WHERE fingerprint = ?", (job.fingerprint,)
        ).fetchone()
        if row is None:
            raise RuntimeError("Gagal mengambil job hasil deduplikasi")
        return int(row["id"]), False

    def save_analysis(
        self,
        job_id: int,
        result: AnalysisResult,
        config_fingerprint: str = "",
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO analyses
            (job_id, score, decision, analysis_mode, provider, model, confidence,
             summary, seniority_level, estimated_years_required, matched_roles,
             required_requirements, preferred_requirements, matched_required,
             missing_required, matched_skills, missing_skills,
             transferable_strengths, red_flags, reasons, config_fingerprint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                result.score,
                result.decision,
                result.analysis_mode,
                result.provider,
                result.model,
                result.confidence,
                result.summary,
                result.seniority_level,
                result.estimated_years_required,
                _json(result.matched_roles),
                _json(result.required_requirements),
                _json(result.preferred_requirements),
                _json(result.matched_required),
                _json(result.missing_required),
                _json(result.matched_skills),
                _json(result.missing_skills),
                _json(result.transferable_strengths),
                _json(result.red_flags),
                _json(result.reasons),
                config_fingerprint,
            ),
        )
        self.connection.commit()

    def save_application(
        self,
        job_id: int,
        status: str,
        mode: str,
        output_path: str,
        package: ApplicationPackageResult | None = None,
        package_config_fingerprint: str = "",
    ) -> None:
        package = package or _empty_package(status, output_path)
        state = lifecycle_for_status(status)
        self.connection.execute(
            """
            INSERT INTO applications
            (job_id, status, mode, output_path, selected_cv_id, selected_cv_path,
             cv_selection_status, cv_selection_score, apply_channel, recipient,
             manifest_path, package_config_fingerprint, lifecycle_state, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                job_id,
                status,
                mode,
                output_path,
                package.selection.cv_id,
                package.selection.source_path,
                package.selection.status,
                package.selection.score,
                package.apply_channel,
                package.recipient,
                package.manifest_path,
                package_config_fingerprint,
                state,
            ),
        )
        self._set_lifecycle_state_in_transaction(job_id, state)
        self.connection.commit()

    def get_latest_analysis_mode(self, job_id: int) -> str:
        row = self.connection.execute(
            "SELECT analysis_mode FROM analyses WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        return str(row["analysis_mode"]) if row else ""

    def get_latest_analysis_config_fingerprint(self, job_id: int) -> str:
        row = self.connection.execute(
            "SELECT config_fingerprint FROM analyses WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        return str(row["config_fingerprint"] or "") if row else ""

    def has_application(self, job_id: int) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM applications WHERE job_id = ? LIMIT 1", (job_id,)
        ).fetchone()
        return row is not None

    def get_latest_application_status(self, job_id: int) -> str:
        row = self.connection.execute(
            "SELECT status FROM applications WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        return str(row["status"]) if row else ""

    def get_latest_application_package_fingerprint(self, job_id: int) -> str:
        row = self.connection.execute(
            """
            SELECT package_config_fingerprint
            FROM applications
            WHERE job_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (job_id,),
        ).fetchone()
        return str(row["package_config_fingerprint"] or "") if row else ""

    def get_latest_analysis(self, job_id: int) -> AnalysisResult | None:
        row = self.connection.execute(
            "SELECT * FROM analyses WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return AnalysisResult(
            score=int(row["score"]),
            decision=str(row["decision"]),
            analysis_mode=str(row["analysis_mode"]),
            provider=str(row["provider"]),
            model=str(row["model"]),
            confidence=int(row["confidence"]),
            summary=str(row["summary"]),
            seniority_level=str(row["seniority_level"]),
            estimated_years_required=int(row["estimated_years_required"]),
            matched_roles=_loads(row["matched_roles"]),
            required_requirements=_loads(row["required_requirements"]),
            preferred_requirements=_loads(row["preferred_requirements"]),
            matched_required=_loads(row["matched_required"]),
            missing_required=_loads(row["missing_required"]),
            matched_skills=_loads(row["matched_skills"]),
            missing_skills=_loads(row["missing_skills"]),
            transferable_strengths=_loads(row["transferable_strengths"]),
            red_flags=_loads(row["red_flags"]),
            reasons=_loads(row["reasons"]),
        )

    def save_or_update_application(
        self,
        job_id: int,
        status: str,
        mode: str,
        output_path: str,
        package: ApplicationPackageResult | None = None,
        package_config_fingerprint: str = "",
    ) -> bool:
        package = package or _empty_package(status, output_path)
        state = lifecycle_for_status(status)
        row = self.connection.execute(
            "SELECT id FROM applications WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        if row is None:
            self.save_application(
                job_id,
                status,
                mode,
                output_path,
                package,
                package_config_fingerprint,
            )
            return True
        self.connection.execute(
            """
            UPDATE applications SET
              status = ?, mode = ?, output_path = ?, selected_cv_id = ?,
              selected_cv_path = ?, cv_selection_status = ?, cv_selection_score = ?,
              apply_channel = ?, recipient = ?, manifest_path = ?,
              package_config_fingerprint = ?, lifecycle_state = ?,
              updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status,
                mode,
                output_path,
                package.selection.cv_id,
                package.selection.source_path,
                package.selection.status,
                package.selection.score,
                package.apply_channel,
                package.recipient,
                package.manifest_path,
                package_config_fingerprint,
                state,
                int(row["id"]),
            ),
        )
        self._set_lifecycle_state_in_transaction(job_id, state)
        self.connection.commit()
        return False

    def _set_lifecycle_state_in_transaction(
        self, job_id: int, state: str, reason: str = ""
    ) -> bool:
        normalized = (state or "NEW").strip().upper() or "NEW"
        job_cursor = self.connection.execute(
            """
            UPDATE jobs
            SET lifecycle_state = ?, lifecycle_updated_at = CURRENT_TIMESTAMP,
                lifecycle_reason = ?
            WHERE id = ?
            """,
            (normalized, reason, job_id),
        )
        app_cursor = self.connection.execute(
            """
            UPDATE applications
            SET lifecycle_state = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = (
                SELECT id FROM applications WHERE job_id = ? ORDER BY id DESC LIMIT 1
            )
            """,
            (normalized, job_id),
        )
        return bool(job_cursor.rowcount or app_cursor.rowcount)

    def set_lifecycle_state(self, job_id: int, state: str) -> bool:
        """Stamp lifecycle on the job and its latest application atomically."""
        updated = self._set_lifecycle_state_in_transaction(job_id, state)
        self.connection.commit()
        return updated

    def get_lifecycle_state(self, job_id: int) -> str:
        row = self.connection.execute(
            "SELECT lifecycle_state FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row and row["lifecycle_state"]:
            return str(row["lifecycle_state"])
        row = self.connection.execute(
            "SELECT lifecycle_state FROM applications WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        return str(row["lifecycle_state"]) if row else ""

    def invalidate_application(self, job_id: int, status: str) -> bool:
        row = self.connection.execute(
            "SELECT id FROM applications WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        if row is None:
            return False
        self.connection.execute(
            "UPDATE applications SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, int(row["id"])),
        )
        self._set_lifecycle_state_in_transaction(job_id, lifecycle_for_status(status))
        self.connection.commit()
        return True

    def get_application(self, application_id: int) -> dict[str, object] | None:
        row = self.connection.execute(
            """
            SELECT ap.*, j.title, j.company, j.url, j.apply_email, j.location
            FROM applications ap
            JOIN jobs j ON j.id = ap.job_id
            WHERE ap.id = ?
            """,
            (application_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_email_queue(self, limit: int = 100) -> list[dict[str, object]]:
        rows = self.connection.execute(
            """
            SELECT ap.*, j.title, j.company, j.url, j.apply_email, j.location
            FROM applications ap
            JOIN jobs j ON j.id = ap.job_id
            WHERE ap.apply_channel = 'EMAIL'
              AND ap.status IN ('DRAFT_READY_EMAIL', 'GMAIL_DRAFT_FAILED')
            ORDER BY ap.id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_portal_queue(self, limit: int = 100) -> list[dict[str, object]]:
        rows = self.connection.execute(
            """
            SELECT ap.*, j.title, j.company, j.url, j.apply_email, j.location
            FROM applications ap
            JOIN jobs j ON j.id = ap.job_id
            WHERE ap.apply_channel = 'PORTAL'
              AND ap.status IN ('DRAFT_READY_PORTAL', 'PORTAL_ASSIST_FAILED')
            ORDER BY ap.id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def update_delivery(
        self,
        application_id: int,
        *,
        status: str,
        gmail_draft_id: str | None = None,
        gmail_message_id: str | None = None,
        approval_code_hash: str | None = None,
        approved: bool = False,
        sent: bool = False,
        portal_report_path: str | None = None,
        last_error: str | None = None,
    ) -> None:
        updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        values: list[object] = [status]
        if gmail_draft_id is not None:
            updates.append("gmail_draft_id = ?")
            values.append(gmail_draft_id)
        if gmail_message_id is not None:
            updates.append("gmail_message_id = ?")
            values.append(gmail_message_id)
        if approval_code_hash is not None:
            updates.append("approval_code_hash = ?")
            values.append(approval_code_hash)
        if approved:
            updates.append("approved_at = CURRENT_TIMESTAMP")
        if sent:
            updates.append("sent_at = CURRENT_TIMESTAMP")
            updates.append("approval_code_hash = ''")
        if portal_report_path is not None:
            updates.append("portal_report_path = ?")
            values.append(portal_report_path)
        if last_error is not None:
            updates.append("last_error = ?")
            values.append(last_error)
        values.append(application_id)
        application = self.connection.execute(
            "SELECT job_id FROM applications WHERE id = ?",
            (application_id,),
        ).fetchone()
        self.connection.execute(
            f"UPDATE applications SET {', '.join(updates)} WHERE id = ?", values
        )
        if application is not None:
            self._set_lifecycle_state_in_transaction(
                int(application["job_id"]), lifecycle_for_status(status)
            )
        self.connection.commit()

    def record_event(
        self,
        event_type: str,
        *,
        application_id: int | None = None,
        job_id: int | None = None,
        status: str = "",
        detail: str = "",
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO application_events
            (application_id, job_id, event_type, status, detail, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                application_id,
                job_id,
                event_type,
                status,
                detail,
                _json(metadata or {}),
            ),
        )
        self.connection.commit()

    def count_events_today(self, event_type: str) -> int:
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM application_events
            WHERE event_type = ?
              AND date(created_at, 'localtime') = date('now', 'localtime')
            """,
            (event_type,),
        ).fetchone()
        return int(row["total"] if row else 0)

    def list_audit(self, limit: int = 50) -> Iterable[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT ev.*, ap.status AS application_status, j.company, j.title
            FROM application_events ev
            LEFT JOIN applications ap ON ap.id = ev.application_id
            LEFT JOIN jobs j ON j.id = COALESCE(ev.job_id, ap.job_id)
            ORDER BY ev.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def create_run(self, started_at: str) -> int:
        cursor = self.connection.execute(
            "INSERT INTO runs (started_at) VALUES (?)", (started_at,)
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def save_collector_reports(self, run_id: int, reports: list[dict[str, object]]) -> None:
        self.connection.executemany(
            """
            INSERT INTO collector_runs
            (run_id, name, collector_type, status, found, duration_ms, message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    str(item.get("name", "")),
                    str(item.get("type", "")),
                    str(item.get("status", "")),
                    int(item.get("found", 0)),
                    int(item.get("duration_ms", 0)),
                    str(item.get("message", "")),
                )
                for item in reports
            ],
        )
        self.connection.commit()

    def finish_run(self, run_id: int, stats: dict[str, object], finished_at: str) -> None:
        self.connection.execute(
            """
            UPDATE runs SET
              finished_at = ?, total_found = ?, raw_found = ?, new_jobs = ?,
              reanalyzed_jobs = ?, duplicates = ?, cross_source_duplicates = ?, apply_count = ?,
              review_count = ?, skip_count = ?, fallback_used = ?, ai_analyzed = ?,
              rule_analyzed = ?, ai_fallbacks = ?, analysis_failures = ?,
              application_ready = ?, application_review_cv = ?, application_blocked = ?,
              email_ready = ?, portal_ready = ?, cv_missing = ?,
              application_rebuilds = ?, reused_analyses = ?, report_path = ?
            WHERE id = ?
            """,
            (
                finished_at,
                int(stats["total_found"]),
                int(stats["raw_found"]),
                int(stats["new_jobs"]),
                int(stats.get("reanalyzed_jobs", 0)),
                int(stats["duplicates"]),
                int(stats["cross_source_duplicates"]),
                int(stats["apply_count"]),
                int(stats["review_count"]),
                int(stats["skip_count"]),
                int(bool(stats["fallback_used"])),
                int(stats.get("ai_analyzed", 0)),
                int(stats.get("rule_analyzed", 0)),
                int(stats.get("ai_fallbacks", 0)),
                int(stats.get("analysis_failures", 0)),
                int(stats.get("application_ready", 0)),
                int(stats.get("application_review_cv", 0)),
                int(stats.get("application_blocked", 0)),
                int(stats.get("email_ready", 0)),
                int(stats.get("portal_ready", 0)),
                int(stats.get("cv_missing", 0)),
                int(stats.get("application_rebuilds", 0)),
                int(stats.get("reused_analyses", 0)),
                str(stats["report_path"]),
                run_id,
            ),
        )
        self.connection.commit()

    def list_jobs(self, limit: int = 20) -> Iterable[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT j.id, j.title, j.company, j.location, j.source, j.remote,
                   j.posted_at, j.created_at, a.score, a.decision,
                   a.analysis_mode, a.confidence, a.seniority_level,
                   j.lifecycle_state
            FROM jobs j
            LEFT JOIN analyses a ON a.id = (
                SELECT MAX(a2.id) FROM analyses a2 WHERE a2.job_id = j.id
            )
            ORDER BY j.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def list_applications(self, limit: int = 20) -> Iterable[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT ap.id, ap.job_id, ap.status, ap.mode, ap.apply_channel,
                   ap.recipient, ap.selected_cv_id, ap.cv_selection_status,
                   ap.cv_selection_score, ap.output_path, ap.gmail_draft_id,
                   ap.gmail_message_id, ap.portal_report_path, ap.last_error,
                   ap.lifecycle_state, ap.package_config_fingerprint,
                   ap.created_at, ap.updated_at, j.company, j.title
            FROM applications ap
            JOIN jobs j ON j.id = ap.job_id
            ORDER BY ap.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: object) -> list[str]:
    try:
        data = json.loads(str(value or "[]"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data]


def _empty_package(status: str, output_path: str) -> ApplicationPackageResult:
    from .models import CVSelection

    return ApplicationPackageResult(
        status=status,
        output_path=output_path,
        apply_channel="",
        recipient="",
        selection=CVSelection(status=""),
    )
