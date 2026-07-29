from __future__ import annotations

import re
from pathlib import Path
from typing import Any

TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def validate_schedule(settings: dict[str, Any]) -> list[str]:
    cfg = settings.get("scheduler", {})
    errors: list[str] = []
    times = cfg.get("run_times", [])
    if not isinstance(times, list) or not times:
        errors.append("scheduler.run_times harus berisi minimal satu waktu HH:MM")
    else:
        for value in times:
            if not TIME_RE.match(str(value)):
                errors.append(f"Waktu scheduler tidak valid: {value}")
    timezone = str(cfg.get("timezone", "Asia/Jakarta"))
    if timezone != "Asia/Jakarta":
        errors.append("KarirLog hanya divalidasi untuk timezone Asia/Jakarta")
    return errors


def build_windows_task_names(settings: dict[str, Any]) -> list[str]:
    times = settings.get("scheduler", {}).get("run_times", [])
    return [f"KarirLog_{str(value).replace(':', '')}" for value in times]


def scheduler_readiness(settings: dict[str, Any], project_root: str | Path = ".") -> list[tuple[str, str]]:
    cfg = settings.get("scheduler", {})
    errors = validate_schedule(settings)
    root = Path(project_root)
    runner = root / "launcher" / "scheduler" / "scheduled_run.bat"
    return [
        ("enabled", "READY" if cfg.get("enabled", False) else "DISABLED"),
        ("schedule", "READY" if not errors else "; ".join(errors)),
        ("runner", "READY" if runner.exists() else "MISSING"),
    ]
