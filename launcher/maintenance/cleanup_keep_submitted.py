from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

KEEP_STATUSES = ("PORTAL_SUBMITTED", "EMAIL_SENT")
JOB_FOLDER_RE = re.compile(r"^job_(\d+)(?:_|$)", re.IGNORECASE)


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def resolve_project_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_settings(root: Path) -> dict[str, Any]:
    settings_path = root / "config" / "settings.json"
    if not settings_path.exists():
        raise FileNotFoundError(f"Settings tidak ditemukan: {settings_path}")
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("config/settings.json harus berupa object JSON")
    return payload


def get_submitted_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    if not table_exists(connection, "applications") or not table_exists(connection, "jobs"):
        return []
    connection.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in KEEP_STATUSES)
    rows = connection.execute(
        f"""
        SELECT ap.*, j.title, j.company, j.url, j.location
        FROM applications ap
        JOIN jobs j ON j.id = ap.job_id
        WHERE ap.status IN ({placeholders})
        ORDER BY ap.id ASC
        """,
        KEEP_STATUSES,
    ).fetchall()
    return [dict(row) for row in rows]


def scalar(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> int:
    row = connection.execute(query, params).fetchone()
    return int(row[0] if row else 0)


def collect_counts(connection: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in ("jobs", "analyses", "applications", "application_events", "runs", "collector_runs"):
        counts[table] = scalar(connection, f"SELECT COUNT(*) FROM {table}") if table_exists(connection, table) else 0
    if table_exists(connection, "applications"):
        placeholders = ",".join("?" for _ in KEEP_STATUSES)
        counts["submitted"] = scalar(
            connection,
            f"SELECT COUNT(*) FROM applications WHERE status IN ({placeholders})",
            KEEP_STATUSES,
        )
        counts["applications_removed"] = counts["applications"] - counts["submitted"]
    else:
        counts["submitted"] = 0
        counts["applications_removed"] = 0
    return counts


def create_backup(
    root: Path,
    connection: sqlite3.Connection,
    submitted_rows: list[dict[str, Any]],
    counts: dict[str, int],
) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = root / "data" / "backups" / f"keep_submitted_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    backup_db = backup_dir / "karirlog_before_cleanup.db"
    with sqlite3.connect(backup_db) as backup_connection:
        connection.backup(backup_connection)
    snapshot = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "keep_statuses": list(KEEP_STATUSES),
        "counts_before": counts,
        "submitted_applications": submitted_rows,
    }
    (backup_dir / "submitted_snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return backup_dir


def delete_database_rows(connection: sqlite3.Connection) -> None:
    placeholders = ",".join("?" for _ in KEEP_STATUSES)
    keep_apps = f"SELECT id FROM applications WHERE status IN ({placeholders})"
    keep_jobs = f"SELECT DISTINCT job_id FROM applications WHERE status IN ({placeholders})"

    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("BEGIN")
    try:
        if table_exists(connection, "application_events"):
            connection.execute(
                f"""
                DELETE FROM application_events
                WHERE (application_id IS NOT NULL AND application_id NOT IN ({keep_apps}))
                   OR (application_id IS NULL AND (job_id IS NULL OR job_id NOT IN ({keep_jobs})))
                """,
                KEEP_STATUSES + KEEP_STATUSES,
            )
        if table_exists(connection, "collector_runs"):
            connection.execute("DELETE FROM collector_runs")
        if table_exists(connection, "runs"):
            connection.execute("DELETE FROM runs")
        if table_exists(connection, "applications"):
            connection.execute(
                f"DELETE FROM applications WHERE status NOT IN ({placeholders})",
                KEEP_STATUSES,
            )
        if table_exists(connection, "analyses"):
            connection.execute(
                f"DELETE FROM analyses WHERE job_id NOT IN ({keep_jobs})",
                KEEP_STATUSES,
            )
        if table_exists(connection, "jobs"):
            connection.execute(
                f"DELETE FROM jobs WHERE id NOT IN ({keep_jobs})",
                KEEP_STATUSES,
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    connection.execute("VACUUM")


def referenced_output_paths(root: Path, output_dir: Path, submitted_rows: list[dict[str, Any]]) -> set[Path]:
    preserved: set[Path] = set()
    fields = ("output_path", "manifest_path", "portal_report_path")
    for row in submitted_rows:
        for field in fields:
            value = str(row.get(field) or "").strip()
            if not value:
                continue
            path = resolve_project_path(root, value).resolve()
            try:
                path.relative_to(output_dir.resolve())
            except ValueError:
                continue
            preserved.add(path)
    return preserved


def child_contains_preserved(child: Path, preserved: set[Path]) -> bool:
    child_resolved = child.resolve()
    for path in preserved:
        try:
            path.relative_to(child_resolved)
            return True
        except ValueError:
            pass
    return False


def clean_output(
    root: Path,
    output_dir: Path,
    submitted_rows: list[dict[str, Any]],
) -> tuple[int, int]:
    if not output_dir.exists():
        return 0, 0
    keep_job_ids = {int(row["job_id"]) for row in submitted_rows}
    preserved = referenced_output_paths(root, output_dir, submitted_rows)
    removed_files = 0
    removed_dirs = 0

    for child in list(output_dir.iterdir()):
        if child.name == ".gitkeep":
            continue
        match = JOB_FOLDER_RE.match(child.name)
        if match and int(match.group(1)) in keep_job_ids:
            continue
        if child_contains_preserved(child, preserved):
            continue
        if child.is_dir():
            shutil.rmtree(child)
            removed_dirs += 1
        else:
            child.unlink()
            removed_files += 1
    return removed_files, removed_dirs


def clean_cache(root: Path) -> bool:
    cache_dir = root / "data" / "cache"
    if not cache_dir.exists():
        return False
    shutil.rmtree(cache_dir)
    return True


def print_preview(counts: dict[str, int], submitted_rows: list[dict[str, Any]]) -> None:
    print("\n=== PREVIEW PEMBERSIHAN DATA ===")
    print(f"Lamaran submitted dipertahankan : {counts['submitted']}")
    print(f"Lamaran lain akan dihapus        : {counts['applications_removed']}")
    print(f"Total lowongan saat ini          : {counts['jobs']}")
    print(f"Total analisis saat ini          : {counts['analyses']}")
    print(f"Histori run akan dikosongkan     : {counts['runs']}")
    print("Cache discovery akan dihapus     : Ya")
    print("Hasil discovery/output non-submit: Akan dihapus")
    print("Profil browser/login             : Tetap")
    print("CV, config, .env, Gmail token    : Tetap")
    print("\nYANG DIPERTAHANKAN")
    if not submitted_rows:
        print("- Tidak ada PORTAL_SUBMITTED atau EMAIL_SENT.")
    for row in submitted_rows:
        print(
            f"- Application #{int(row['id']):03} | {row['status']} | "
            f"{row.get('company', '-')} — {row.get('title', '-')}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bersihkan KarirLog dan pertahankan hanya lamaran yang sudah terkirim."
    )
    parser.add_argument("--apply", action="store_true", help="Terapkan pembersihan")
    parser.add_argument("--root", default="", help="Root project untuk testing")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[2]
    settings = load_settings(root)
    database_path = resolve_project_path(root, str(settings.get("database_path", "data/karirlog.db")))
    output_dir = resolve_project_path(root, str(settings.get("output_dir", "data/output")))

    if not database_path.exists():
        print(f"Database belum tersedia: {database_path}")
        return 2

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        submitted_rows = get_submitted_rows(connection)
        counts = collect_counts(connection)
        print_preview(counts, submitted_rows)

        if not args.apply:
            print("\nMode preview: belum ada data yang diubah.")
            return 0

        backup_dir = create_backup(root, connection, submitted_rows, counts)
        delete_database_rows(connection)
        removed_files, removed_dirs = clean_output(root, output_dir, submitted_rows)
        cache_removed = clean_cache(root)
        counts_after = collect_counts(connection)

        result = {
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "backup_dir": str(backup_dir),
            "kept_statuses": list(KEEP_STATUSES),
            "counts_before": counts,
            "counts_after": counts_after,
            "output_removed_files": removed_files,
            "output_removed_directories": removed_dirs,
            "cache_removed": cache_removed,
        }
        (backup_dir / "cleanup_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        print("\n=== PEMBERSIHAN SELESAI ===")
        print(f"Lamaran submitted tersisa : {counts_after['applications']}")
        print(f"Lowongan tersisa          : {counts_after['jobs']}")
        print(f"Analisis tersisa           : {counts_after['analyses']}")
        print(f"Output dihapus             : {removed_files} file, {removed_dirs} folder")
        print(f"Cache discovery dihapus    : {'Ya' if cache_removed else 'Tidak ada'}")
        print(f"Backup lengkap             : {backup_dir}")
        print("\nLive Update berikutnya akan mencari data baru dari awal.")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
