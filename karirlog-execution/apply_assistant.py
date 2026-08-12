"""One-command KarirLog Execution + application assistance.

Daily flow:
    reviewed CSV -> analyze/trust -> build packages -> Gmail drafts -> portal queue

The private candidate profile stays local. Public execution focus rules are
merged into a temporary runtime profile and deleted after the run.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT.parent / "karirlog-contracts" / "src"))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

import main as execution_main
import karirlog_execution.application_builder as application_builder
import karirlog_execution.pipeline as execution_pipeline
from karirlog_execution.models import AnalysisResult, Job


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _dedupe_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        value = str(raw).strip()
        marker = value.casefold()
        if not value or marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result


def build_active_profile(
    private_profile: dict[str, Any],
    focus_config: dict[str, Any],
) -> dict[str, Any]:
    """Overlay public job-search focuses without mutating private profile data."""
    active = copy.deepcopy(private_profile)
    focuses = [
        item
        for item in focus_config.get("focuses", [])
        if isinstance(item, dict)
    ]
    if not focuses:
        raise ValueError("execution focus config tidak memiliki focuses")

    target_roles: list[Any] = []
    added_transferable: list[Any] = []
    focus_metadata: list[dict[str, Any]] = []

    for focus in focuses:
        roles = list(focus.get("roles", []))
        aliases = list(focus.get("runtime_role_aliases", []))
        transferable = list(focus.get("transferable_skills", []))
        target_roles.extend(roles)
        target_roles.extend(aliases)
        added_transferable.extend(transferable)
        focus_metadata.append(
            {
                "id": str(focus.get("id", "")).strip(),
                "label": str(focus.get("label", "")).strip(),
                "weight": focus.get("weight", 0),
                "roles": _dedupe_strings(roles),
            }
        )

    active["target_roles"] = _dedupe_strings(target_roles)
    active["transferable_skills"] = _dedupe_strings(
        list(active.get("transferable_skills", [])) + added_transferable
    )
    active["skill_catalog"] = _dedupe_strings(
        list(active.get("skill_catalog", [])) + added_transferable
    )
    active["execution_focuses"] = focus_metadata
    return active


def _write_runtime_profile(profile: dict[str, Any]) -> Path:
    runtime_dir = _ROOT / "data" / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        prefix="candidate_profile_active_",
        dir=runtime_dir,
        delete=False,
    )
    try:
        json.dump(profile, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        return Path(handle.name)
    finally:
        handle.close()


def trusted_csv_analysis(
    job: Job,
    profile: dict[str, Any],
    settings: dict[str, Any],
) -> AnalysisResult:
    """Trust a manually reviewed CSV row without invoking AI or the rule engine."""
    del profile, settings
    return AnalysisResult(
        score=100,
        decision="APPLY",
        analysis_mode="TRUSTED_CSV",
        provider="manual_review",
        model="",
        confidence=100,
        summary=(
            "Lowongan diterima dari CSV yang sudah direview. "
            "AI dan rule engine dilewati untuk run ini."
        ),
        seniority_level="REVIEWED_INPUT",
        estimated_years_required=0,
        matched_roles=[job.title] if job.title.strip() else [],
        reasons=[
            "Trusted CSV mode: baris input dianggap sudah lolos review manual.",
            "Decision dikunci APPLY tanpa panggilan OpenAI dan tanpa scoring rule.",
        ],
    )


def portal_only_destination(job: Job) -> tuple[str, str, list[str]]:
    """Force a valid job URL to be used as the apply destination, ignoring email."""
    url = job.url.strip()
    warnings: list[str] = []
    if job.apply_email.strip():
        warnings.append("Mode portal-only aktif: apply_email diabaikan untuk run ini")
    if url.lower().startswith(("http://", "https://")):
        return "PORTAL", url, warnings
    warnings.append("Mode portal-only membutuhkan URL apply yang valid")
    return "UNAVAILABLE", "", warnings


def run_assistant(args: argparse.Namespace) -> int:
    if load_dotenv is not None:
        load_dotenv(_ROOT / ".env", override=True)

    profile_path = Path(args.profile).resolve()
    settings_path = Path(args.settings).resolve()
    if not profile_path.is_file():
        print(f"ERROR: candidate profile lokal tidak ditemukan: {profile_path}")
        return 2
    if not settings_path.is_file():
        print(f"ERROR: execution settings tidak ditemukan: {settings_path}")
        return 2

    private_profile = _load_json(profile_path)
    settings = _load_json(settings_path)
    focus_path = Path(
        str(settings.get("execution_focus_config", "config/execution_focuses.json"))
    )
    if not focus_path.is_absolute():
        focus_path = (_ROOT / focus_path).resolve()
    if not focus_path.is_file():
        print(f"ERROR: execution focus config tidak ditemukan: {focus_path}")
        return 2

    try:
        active_profile = build_active_profile(private_profile, _load_json(focus_path))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: gagal membangun active profile: {exc}")
        return 2

    runtime_profile = _write_runtime_profile(active_profile)
    assistant_cfg = settings.get("apply_assistant", {})
    execution_rc = 2
    gmail_status = "SKIPPED"
    portal_status = "SKIPPED"

    requested_mode = str(args.analysis_mode or settings.get("analysis_mode", "ai_with_fallback"))
    trusted_mode = requested_mode == "trusted_csv"
    original_analyze_job = execution_pipeline.analyze_job
    original_destination = application_builder.resolve_apply_destination

    if trusted_mode:
        execution_pipeline.analyze_job = trusted_csv_analysis
    if args.portal_only:
        application_builder.resolve_apply_destination = portal_only_destination

    try:
        print("KARIRLOG APPLY ASSISTANT")
        print("=======================")
        print(f"Input CSV      : {args.input or settings.get('input_csv', 'data/input/discovery_latest.csv')}")
        if trusted_mode:
            print("Analysis       : TRUSTED CSV - AI OFF, RULE OFF, semua baris -> APPLY")
        elif requested_mode == "rule_only":
            print("Analysis       : RULE ONLY - OpenAI OFF")
        else:
            print(f"Analysis       : {requested_mode}")
        print("Focus          : Core Experience + General Transferable")
        if args.portal_only:
            print("Apply channel  : PORTAL ONLY - apply_email diabaikan")
        else:
            print("Apply channel  : AUTO - email bila valid, selain itu portal")
        print(
            "Delivery       : "
            + ("Gmail SKIP | " if args.skip_gmail else "Gmail ON | ")
            + ("Portal SKIP" if args.skip_portal else "Portal ON")
        )
        print()

        execution_rc = execution_main.command_execute(
            str(runtime_profile),
            str(settings_path),
            args.input,
            requested_mode,
            force_reprocess=bool(args.force_reprocess),
            rebuild_packages=bool(args.rebuild_packages),
        )

        if not args.skip_gmail and assistant_cfg.get("auto_create_gmail_drafts", True):
            try:
                limit = max(1, int(args.gmail_limit or assistant_cfg.get("gmail_limit", 10)))
                gmail_rc = execution_main.command_create_gmail_drafts(
                    str(runtime_profile),
                    str(settings_path),
                    limit,
                )
                gmail_status = "OK" if gmail_rc == 0 else "PERLU CEK"
            except Exception as exc:
                gmail_status = f"PERLU CEK: {exc}"
                print(f"\nGmail draft warning: {exc}")

        if not args.skip_portal and assistant_cfg.get("auto_assist_portal_queue", True):
            try:
                limit = max(1, int(args.portal_limit or assistant_cfg.get("portal_limit", 50)))
                portal_rc = execution_main.command_assist_portal_queue(
                    str(runtime_profile),
                    str(settings_path),
                    limit,
                )
                portal_status = "OK" if portal_rc == 0 else "PERLU CEK"
            except Exception as exc:
                portal_status = f"PERLU CEK: {exc}"
                print(f"\nPortal assist warning: {exc}")

        print("\nKARIRLOG APPLY ASSISTANT — SELESAI")
        print(f"Analysis/package : {'OK' if execution_rc == 0 else 'PERLU CEK'}")
        print(f"Gmail draft      : {gmail_status}")
        print(f"Portal assist    : {portal_status}")
        print("Final submit tetap kamu konfirmasi sendiri.")
        return execution_rc
    finally:
        execution_pipeline.analyze_job = original_analyze_job
        application_builder.resolve_apply_destination = original_destination
        try:
            runtime_profile.unlink(missing_ok=True)
        except OSError:
            pass


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KarirLog one-command Execution + application assistant"
    )
    parser.add_argument("--input", default=None)
    parser.add_argument(
        "--profile",
        default=str(_ROOT / "config" / "candidate_profile.json"),
    )
    parser.add_argument(
        "--settings",
        default=str(_ROOT / "config" / "execution_settings.json"),
    )
    parser.add_argument(
        "--analysis-mode",
        choices=["rule_only", "ai_with_fallback", "ai_required", "trusted_csv"],
    )
    parser.add_argument("--force-reprocess", action="store_true")
    parser.add_argument("--rebuild-packages", action="store_true")
    parser.add_argument(
        "--portal-only",
        action="store_true",
        help="Paksa memakai URL portal dan abaikan apply_email untuk run ini",
    )
    parser.add_argument(
        "--portal-limit",
        type=int,
        default=None,
        help="Override jumlah maksimum portal queue untuk run ini",
    )
    parser.add_argument(
        "--gmail-limit",
        type=int,
        default=None,
        help="Override jumlah maksimum Gmail draft untuk run ini",
    )
    parser.add_argument(
        "--skip-gmail",
        action="store_true",
        help="Lewati pembuatan Gmail draft untuk run ini",
    )
    parser.add_argument(
        "--skip-portal",
        action="store_true",
        help="Lewati portal assistant untuk run ini",
    )
    return parser


def main() -> int:
    return run_assistant(make_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
