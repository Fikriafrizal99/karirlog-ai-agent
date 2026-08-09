from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import requests

from .models import Job


class AIAnalysisError(RuntimeError):
    """AI analysis could not be completed safely."""


ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "summary": {"type": "string"},
        "seniority_level": {
            "type": "string",
            "enum": ["INTERNSHIP", "ENTRY", "JUNIOR", "MID", "SUPERVISOR", "SENIOR", "LEAD", "MANAGER", "UNKNOWN"],
        },
        "estimated_years_required": {"type": "integer", "minimum": 0, "maximum": 30},
        "matched_roles": {"type": "array", "items": {"type": "string"}},
        "required_requirements": {"type": "array", "items": {"type": "string"}},
        "preferred_requirements": {"type": "array", "items": {"type": "string"}},
        "matched_required": {"type": "array", "items": {"type": "string"}},
        "missing_required": {"type": "array", "items": {"type": "string"}},
        "matched_skills": {"type": "array", "items": {"type": "string"}},
        "missing_skills": {"type": "array", "items": {"type": "string"}},
        "transferable_strengths": {"type": "array", "items": {"type": "string"}},
        "red_flags": {"type": "array", "items": {"type": "string"}},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "recommended_action": {"type": "string", "enum": ["APPLY", "REVIEW", "SKIP"]},
    },
    "required": [
        "score",
        "confidence",
        "summary",
        "seniority_level",
        "estimated_years_required",
        "matched_roles",
        "required_requirements",
        "preferred_requirements",
        "matched_required",
        "missing_required",
        "matched_skills",
        "missing_skills",
        "transferable_strengths",
        "red_flags",
        "reasons",
        "recommended_action",
    ],
}


@dataclass(slots=True)
class AIProviderResult:
    data: dict[str, Any]
    provider: str
    model: str


class OpenAIJobAnalyzer:
    def __init__(self, settings: dict[str, Any], session: requests.Session | None = None):
        self.api_key_env = str(settings.get("openai_api_key_env", "OPENAI_API_KEY"))
        self.api_key = os.getenv(self.api_key_env, "").strip()
        self.model = str(settings.get("ai_model", "gpt-5-mini")).strip()
        self.endpoint = str(
            settings.get("openai_responses_url", "https://api.openai.com/v1/responses")
        ).strip()
        self.timeout = int(settings.get("ai_timeout_seconds", 45))
        self.max_output_tokens = int(settings.get("ai_max_output_tokens", 2200))
        self.strategy = str(settings.get("analysis_strategy", "balanced")).strip()
        self.session = session or requests.Session()

    @property
    def ready(self) -> bool:
        return bool(self.api_key and self.model and self.endpoint)

    def analyze(self, job: Job, profile: dict[str, Any]) -> AIProviderResult:
        if not self.ready:
            raise AIAnalysisError(f"API key belum tersedia pada environment {self.api_key_env}")

        payload = {
            "model": self.model,
            "store": False,
            "max_output_tokens": self.max_output_tokens,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Anda adalah job-fit analyst yang evidence-based dan opportunity-oriented. "
                                f"Strategi aktif: {self.strategy}. Tujuan utama adalah membantu kandidat melamar "
                                "sebanyak mungkin lowongan yang masih masuk akal, tanpa mengarang pengalaman, "
                                "sertifikasi, pendidikan, skill, atau persyaratan. Jangan menuntut kecocokan judul "
                                "jabatan yang sama persis. Pengalaman langsung dan transferable skills yang relevan "
                                "boleh menjadi dasar kuat untuk APPLY, terutama pada role operations, project/program "
                                "coordination, business support, partnership, commercial, customer/client, dan process "
                                "improvement. Bedakan tegas persyaratan wajib dari preferred/nice-to-have. Preferred "
                                "requirements tidak boleh dimasukkan ke missing_required dan tidak boleh sendiri "
                                "menurunkan kandidat menjadi REVIEW atau SKIP. Kekurangan minor seperti tools yang "
                                "mudah dipelajari, pengalaman industri yang hanya preferensi, atau wording role yang "
                                "berbeda cukup mengurangi skor secara moderat. Rekomendasikan APPLY jika kandidat "
                                "cukup kompetitif berdasarkan pengalaman langsung atau transferable skills dan tidak "
                                "ada blocker nyata. Gunakan REVIEW hanya jika ada ketidakpastian material yang memang "
                                "perlu diperiksa manusia. Gunakan SKIP hanya untuk mismatch berat: scam, seniority atau "
                                "years requirement terlalu jauh, role jelas tidak relevan, atau hard technical/mandatory "
                                "requirement yang benar-benar tidak dimiliki. Transferable skill tidak boleh dianggap "
                                "menggantikan hard technical requirement. Output wajib mengikuti JSON schema."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                {
                                    "candidate_profile": _safe_profile(profile),
                                    "job": {
                                        "title": job.title,
                                        "company": job.company,
                                        "location": job.location,
                                        "description": job.description,
                                        "employment_type": job.employment_type,
                                        "salary": job.salary,
                                        "remote": job.remote,
                                        "source": job.source,
                                    },
                                },
                                ensure_ascii=False,
                            ),
                        }
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "job_fit_analysis",
                    "description": "Structured candidate-to-job fit analysis",
                    "strict": True,
                    "schema": ANALYSIS_SCHEMA,
                }
            },
        }

        try:
            response = self.session.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise AIAnalysisError(f"Koneksi OpenAI gagal: {exc}") from exc

        if response.status_code >= 400:
            detail = _safe_error_text(response)
            raise AIAnalysisError(f"OpenAI HTTP {response.status_code}: {detail}")

        try:
            body = response.json()
        except ValueError as exc:
            raise AIAnalysisError("Respons OpenAI bukan JSON valid") from exc

        output_text = _extract_output_text(body)
        if not output_text:
            raise AIAnalysisError("Respons OpenAI tidak memiliki output_text")
        try:
            data = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise AIAnalysisError("Structured output OpenAI tidak dapat dibaca") from exc
        if not isinstance(data, dict):
            raise AIAnalysisError("Structured output OpenAI bukan object")
        _validate_required_fields(data)
        return AIProviderResult(data=data, provider="openai", model=self.model)


def _safe_profile(profile: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "location",
        "target_roles",
        "preferred_locations",
        "skills",
        "transferable_skills",
        "experience_summary",
        "education",
        "career_level",
        "years_experience_target_domain",
        "max_years_required",
        "languages",
        "excluded_role_keywords",
    )
    return {key: profile.get(key) for key in allowed if key in profile}


def _extract_output_text(body: dict[str, Any]) -> str:
    direct = body.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    output = body.get("output", [])
    if not isinstance(output, list):
        return ""
    chunks: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                chunks.append(part["text"])
    return "".join(chunks).strip()


def _validate_required_fields(data: dict[str, Any]) -> None:
    required = set(ANALYSIS_SCHEMA["required"])
    missing = sorted(required - set(data))
    if missing:
        raise AIAnalysisError("Field structured output hilang: " + ", ".join(missing))


def _safe_error_text(response: requests.Response) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])[:300]
    except ValueError:
        pass
    return response.text.strip()[:300] or "tanpa detail"
