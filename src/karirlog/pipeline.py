from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .ai_provider import AIAnalysisError
from .analysis import analyze_job
from .application_builder import build_application
from .config import load_json
from .database import Database
from .discovery import DiscoveryManager
from .models import AnalysisResult, ApplicationPackageResult
from .notifications import build_summary, send_telegram


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def run_pipeline(profile: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    started_at = now_iso()
    database = Database(settings["database_path"])
    run_id = database.create_run(started_at)

    stats: dict[str, Any] = {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": "",
        "discovery_mode": settings.get("discovery_mode", "live_with_fallback"),
        "analysis_mode": settings.get("analysis_mode", "ai_with_fallback"),
        "ai_model": settings.get("ai_model", ""),
        "profile_career_level": profile.get("career_level", ""),
        "profile_years_experience_target_domain": profile.get("years_experience_target_domain", 0),
        "profile_max_years_required": profile.get("max_years_required", 0),
        "raw_found": 0,
        "total_found": 0,
        "new_jobs": 0,
        "reanalyzed_jobs": 0,
        "reused_analyses": 0,
        "duplicates": 0,
        "cross_source_duplicates": 0,
        "fallback_used": False,
        "apply_count": 0,
        "review_count": 0,
        "skip_count": 0,
        "ai_analyzed": 0,
        "rule_analyzed": 0,
        "ai_fallbacks": 0,
        "analysis_failures": 0,
        "applications_updated": 0,
        "applications_invalidated": 0,
        "application_rebuilds": 0,
        "application_ready": 0,
        "application_review_cv": 0,
        "application_review_document": 0,
        "attachment_files": 0,
        "application_blocked": 0,
        "email_ready": 0,
        "portal_ready": 0,
        "cv_missing": 0,
        "auto_apply_mode": settings.get("auto_apply_mode", "draft_only"),
        "report_path": "",
        "collectors": [],
        "results": [],
    }

    try:
        sources_path = str(settings.get("sources_config", "config/sources.json"))
        sources_config = load_json(sources_path)
        discovery = DiscoveryManager(profile, settings, sources_config).collect()
        stats["raw_found"] = discovery.raw_found
        stats["total_found"] = len(discovery.jobs)
        stats["cross_source_duplicates"] = discovery.cross_source_duplicates
        stats["fallback_used"] = discovery.fallback_used
        stats["collectors"] = [report.to_dict() for report in discovery.reports]
        database.save_collector_reports(run_id, stats["collectors"])

        build_for = set(settings.get("build_application_for", ["APPLY"]))
        for job in discovery.jobs:
            job_id, is_new = database.insert_job(job)
            job.id = job_id
            result: AnalysisResult | None = None
            reused_analysis = False

            if is_new:
                stats["new_jobs"] += 1
            else:
                latest_mode = database.get_latest_analysis_mode(job_id)
                if _should_reanalyze_existing(latest_mode, settings):
                    stats["reanalyzed_jobs"] += 1
                else:
                    latest_result = database.get_latest_analysis(job_id)
                    application_status = database.get_latest_application_status(job_id)
                    if _should_rebuild_application(
                        latest_result, application_status, build_for, settings
                    ):
                        result = latest_result
                        reused_analysis = True
                        stats["reused_analyses"] += 1
                        stats["application_rebuilds"] += 1
                    else:
                        stats["duplicates"] += 1
                        continue

            if result is None:
                try:
                    result = analyze_job(job, profile, settings)
                except AIAnalysisError as exc:
                    stats["analysis_failures"] += 1
                    stats["results"].append(
                        {
                            "job_id": job_id,
                            "title": job.title,
                            "company": job.company,
                            "location": job.location,
                            "source": job.source,
                            "url": job.url,
                            "analysis_error": str(exc),
                            "decision": "ERROR",
                            "score": 0,
                            "output_path": "",
                            "application_status": "NOT_BUILT",
                        }
                    )
                    continue

                database.save_analysis(job_id, result)
                if result.analysis_mode == "AI":
                    stats["ai_analyzed"] += 1
                else:
                    stats["rule_analyzed"] += 1
                    if result.analysis_mode == "RULE_FALLBACK":
                        stats["ai_fallbacks"] += 1

            stats[f"{result.decision.lower()}_count"] += 1
            output_path = ""
            package: ApplicationPackageResult | None = None
            if result.decision in build_for:
                package = build_application(
                    settings["output_dir"], job_id, job, result, profile, settings
                )
                output_path = package.output_path
                created = database.save_or_update_application(
                    job_id,
                    status=package.status,
                    mode=str(settings.get("auto_apply_mode", "draft_only")),
                    output_path=output_path,
                    package=package,
                )
                if not created:
                    stats["applications_updated"] += 1
                database.record_event(
                    "APPLICATION_PACKAGE_BUILT",
                    application_id=int(
                        database.connection.execute(
                            "SELECT id FROM applications WHERE job_id = ? ORDER BY id DESC LIMIT 1",
                            (job_id,),
                        ).fetchone()["id"]
                    ),
                    job_id=job_id,
                    status=package.status,
                    detail=f"Paket lamaran dibangun untuk channel {package.apply_channel}",
                    metadata={
                        "output_path": output_path,
                        "cv_id": package.selection.cv_id,
                        "document_profile": package.document_selection.profile_id,
                        "attachment_count": len(package.attached_files),
                    },
                )
                _count_application_status(stats, package)
            elif database.invalidate_application(job_id, "INVALIDATED_BY_REANALYSIS"):
                stats["applications_invalidated"] += 1

            result_item: dict[str, Any] = {
                "job_id": job_id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "source": job.source,
                "url": job.url,
                "score": result.score,
                "decision": result.decision,
                "analysis_mode": result.analysis_mode,
                "analysis_reused": reused_analysis,
                "provider": result.provider,
                "model": result.model,
                "confidence": result.confidence,
                "summary": result.summary,
                "seniority_level": result.seniority_level,
                "estimated_years_required": result.estimated_years_required,
                "matched_roles": result.matched_roles,
                "required_requirements": result.required_requirements,
                "matched_required": result.matched_required,
                "matched_skills": result.matched_skills,
                "missing_required": result.missing_required,
                "transferable_strengths": result.transferable_strengths,
                "red_flags": result.red_flags,
                "reasons": result.reasons,
                "output_path": output_path,
                "application_status": package.status if package else "NOT_BUILT",
            }
            if package:
                result_item.update(
                    {
                        "apply_channel": package.apply_channel,
                        "recipient": package.recipient,
                        "selected_cv_id": package.selection.cv_id,
                        "selected_cv_label": package.selection.label,
                        "selected_cv_path": package.selection.source_path,
                        "cv_selection_status": package.selection.status,
                        "cv_selection_score": package.selection.score,
                        "cv_selection_confidence": package.selection.confidence,
                        "cv_selection_reasons": package.selection.reasons,
                        "cv_warnings": package.selection.warnings,
                        "manifest_path": package.manifest_path,
                        "attached_cv_path": package.attached_cv_path,
                        "attached_files": package.attached_files,
                        "document_selection_status": package.document_selection.status,
                        "document_profile_id": package.document_selection.profile_id,
                        "automatic_attachment_count": len(package.document_selection.automatic_attachments),
                        "supporting_document_count": len(package.document_selection.selected_supporting_documents),
                        "document_warnings": package.document_selection.warnings,
                    }
                )
            stats["results"].append(result_item)

        stats["finished_at"] = now_iso()
        output_dir = Path(settings["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / f"run_{run_id}_report.json"
        stats["report_path"] = str(report_path)
        report_path.write_text(
            json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        database.finish_run(run_id, stats, stats["finished_at"])

        summary = build_summary(stats)
        telegram_sent, telegram_message = send_telegram(settings, summary)
        stats["telegram_sent"] = telegram_sent
        stats["telegram_message"] = telegram_message
        return stats
    finally:
        database.close()


def _count_application_status(
    stats: dict[str, Any], package: ApplicationPackageResult
) -> None:
    stats["attachment_files"] += len(package.attached_files)
    if package.ready:
        stats["application_ready"] += 1
        if package.apply_channel == "EMAIL":
            stats["email_ready"] += 1
        elif package.apply_channel == "PORTAL":
            stats["portal_ready"] += 1
        return
    if package.status in {"REVIEW_CV", "REVIEW_MULTIPLE_CV"}:
        stats["application_review_cv"] += 1
    elif package.status in {"REVIEW_DOCUMENT", "REVIEW_ATTACHMENT_SIZE"}:
        stats["application_review_document"] += 1
    else:
        stats["application_blocked"] += 1
    if package.status == "BLOCKED_CV_MISSING":
        stats["cv_missing"] += 1


def _should_reanalyze_existing(latest_mode: str, settings: dict[str, Any]) -> bool:
    if not latest_mode:
        return True
    desired_mode = str(settings.get("analysis_mode", "ai_with_fallback")).lower()
    if desired_mode == "rule_only":
        return False
    if not bool(settings.get("reanalyze_fallback_when_ai_ready", True)):
        return False
    env_name = str(settings.get("openai_api_key_env", "OPENAI_API_KEY"))
    ai_ready = bool(os.getenv(env_name, "").strip())
    return ai_ready and latest_mode in {"RULE_ONLY", "RULE_FALLBACK"}


def _should_rebuild_application(
    result: AnalysisResult | None,
    application_status: str,
    build_for: set[str],
    settings: dict[str, Any],
) -> bool:
    if result is None or result.decision not in build_for:
        return False
    if bool(settings.get("force_rebuild_application_packages", False)):
        return True
    if not bool(settings.get("rebuild_incomplete_applications", True)):
        return False
    rebuild_statuses = {
        "",
        "DRAFT_READY",  # legacy V0.1-V0.3 package
        "REVIEW_CV",
        "REVIEW_MULTIPLE_CV",
        "REVIEW_DOCUMENT",
        "REVIEW_ATTACHMENT_SIZE",
        "BLOCKED_INVALID_FILE",
        "BLOCKED_CV_LIBRARY",
        "BLOCKED_CV_MISSING",
        "BLOCKED_DESTINATION",
    }
    return application_status in rebuild_statuses
