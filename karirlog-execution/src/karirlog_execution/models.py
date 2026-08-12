from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Job is the shared contract with the Search Engine — imported here so every
# `from .models import Job` in the execution package uses the same type.
from karirlog_contracts.job import Job  # noqa: F401  (re-exported)


@dataclass(slots=True)
class AnalysisResult:
    score: int
    decision: str
    analysis_mode: str = "RULE_ONLY"
    provider: str = "local"
    model: str = ""
    confidence: int = 0
    summary: str = ""
    seniority_level: str = "UNKNOWN"
    estimated_years_required: int = 0
    matched_roles: list[str] = field(default_factory=list)
    required_requirements: list[str] = field(default_factory=list)
    preferred_requirements: list[str] = field(default_factory=list)
    matched_required: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    transferable_strengths: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "decision": self.decision,
            "analysis_mode": self.analysis_mode,
            "provider": self.provider,
            "model": self.model,
            "confidence": self.confidence,
            "summary": self.summary,
            "seniority_level": self.seniority_level,
            "estimated_years_required": self.estimated_years_required,
            "matched_roles": self.matched_roles,
            "required_requirements": self.required_requirements,
            "preferred_requirements": self.preferred_requirements,
            "matched_required": self.matched_required,
            "missing_required": self.missing_required,
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "transferable_strengths": self.transferable_strengths,
            "red_flags": self.red_flags,
            "reasons": self.reasons,
        }


@dataclass(slots=True)
class CVSelection:
    status: str
    cv_id: str = ""
    label: str = ""
    source_path: str = ""
    score: int = 0
    confidence: int = 0
    file_size: int = 0
    sha256: str = ""
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.status == "READY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "cv_id": self.cv_id,
            "label": self.label,
            "source_path": self.source_path,
            "score": self.score,
            "confidence": self.confidence,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "candidates": self.candidates,
        }


@dataclass(slots=True)
class DocumentSelection:
    status: str = "NOT_EVALUATED"
    profile_id: str = ""
    selected_cv: dict[str, Any] = field(default_factory=dict)
    automatic_attachments: list[dict[str, Any]] = field(default_factory=list)
    selected_supporting_documents: list[dict[str, Any]] = field(default_factory=list)
    rejected_files: list[dict[str, Any]] = field(default_factory=list)
    duplicate_files: list[dict[str, Any]] = field(default_factory=list)
    required_document_types: list[str] = field(default_factory=list)
    missing_required_document_types: list[str] = field(default_factory=list)
    total_file_count: int = 0
    total_size_bytes: int = 0
    selection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.status == "READY"

    @property
    def selected_files(self) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        if self.selected_cv:
            files.append(self.selected_cv)
        files.extend(self.automatic_attachments)
        files.extend(self.selected_supporting_documents)
        return files

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "profile_id": self.profile_id,
            "selected_cv": self.selected_cv,
            "automatic_attachments": self.automatic_attachments,
            "selected_supporting_documents": self.selected_supporting_documents,
            "rejected_files": self.rejected_files,
            "duplicate_files": self.duplicate_files,
            "required_document_types": self.required_document_types,
            "missing_required_document_types": self.missing_required_document_types,
            "total_file_count": self.total_file_count,
            "total_size_bytes": self.total_size_bytes,
            "selection_reasons": self.selection_reasons,
            "warnings": self.warnings,
        }


@dataclass(slots=True)
class ApplicationPackageResult:
    status: str
    output_path: str
    apply_channel: str
    recipient: str
    selection: CVSelection
    document_selection: DocumentSelection = field(default_factory=DocumentSelection)
    manifest_path: str = ""
    attached_cv_path: str = ""
    attached_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    package_config_fingerprint: str = ""

    @property
    def ready(self) -> bool:
        return self.status in {"DRAFT_READY_EMAIL", "DRAFT_READY_PORTAL"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "output_path": self.output_path,
            "apply_channel": self.apply_channel,
            "recipient": self.recipient,
            "manifest_path": self.manifest_path,
            "attached_cv_path": self.attached_cv_path,
            "attached_files": self.attached_files,
            "warnings": self.warnings,
            "package_config_fingerprint": self.package_config_fingerprint,
            "cv_selection": self.selection.to_dict(),
            "document_selection": self.document_selection.to_dict(),
        }


@dataclass(slots=True)
class CollectorReport:
    name: str
    collector_type: str
    status: str
    found: int = 0
    duration_ms: int = 0
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.collector_type,
            "status": self.status,
            "found": self.found,
            "duration_ms": self.duration_ms,
            "message": self.message,
        }


@dataclass(slots=True)
class DiscoveryResult:
    jobs: list[Job] = field(default_factory=list)
    reports: list[CollectorReport] = field(default_factory=list)
    raw_found: int = 0
    cross_source_duplicates: int = 0
    fallback_used: bool = False
