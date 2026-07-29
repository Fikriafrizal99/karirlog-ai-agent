from __future__ import annotations

import re
from typing import Any, Iterable

from .ai_provider import AIAnalysisError, OpenAIJobAnalyzer
from .models import AnalysisResult, Job


WORD_RE = re.compile(r"[a-zA-Z0-9+#./-]+")
SENTENCE_RE = re.compile(r"(?<=[.!?;])\s+|\n+")
YEAR_TOKEN_RE = re.compile(
    r"\b(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?\s*(?:\+\s*)?(?:tahun|thn|years?|yrs?)\b",
    re.I,
)
EXPERIENCE_MARKERS = (
    "pengalaman",
    "pengalaman kerja",
    "berpengalaman",
    "experience",
    "work experience",
    "years of experience",
)
AGE_MARKERS = (
    "usia",
    "umur",
    "age",
    "maksimal usia",
    "usia maksimal",
    "maximum age",
)
REQUIRED_MARKERS = (
    "wajib",
    "harus",
    "required",
    "requirement",
    "minimum",
    "minimal",
    "membutuhkan",
    "memiliki pengalaman",
    "menguasai",
    "proficient",
    "must have",
)
PREFERRED_MARKERS = (
    "nilai tambah",
    "lebih disukai",
    "preferred",
    "nice to have",
    "menjadi plus",
    "is a plus",
    "advantage",
)
SCAM_MARKERS = (
    "biaya pendaftaran",
    "biaya administrasi",
    "transfer uang",
    "bayar untuk melamar",
    "registration fee",
    "application fee",
    "security deposit",
)

SENIORITY_KEYWORDS = {
    "MANAGER": (
        "manager",
        "branch manager",
        "sales manager",
        "marketing manager",
        "general manager",
        "head of",
        "kepala divisi",
    ),
    "SUPERVISOR": (
        "supervisor",
        "team leader",
        "team lead",
        "branch marketing head",
        "marketing head",
        "sales head",
        "unit head",
    ),
    "LEAD": ("technical lead", "lead developer", "lead consultant", "project lead"),
    "SENIOR": ("senior", "sr.", "principal", "expert"),
    "MID": (
        "mid level",
        "middle",
        "intermediate",
        "officer",
        "executive",
        "coordinator",
    ),
    "JUNIOR": ("junior", "jr.", "associate"),
    "ENTRY": ("entry level", "fresh graduate", "career switcher", "trainee", "management trainee"),
    "INTERNSHIP": ("intern", "internship", "magang"),
}

# Canonical skills can match common Indonesian/English wording in job descriptions.
SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Sales": ("sales", "penjualan", "selling"),
    "Multifinance": ("multifinance", "multi finance", "leasing", "perusahaan pembiayaan"),
    "Consumer Financing": (
        "consumer financing",
        "consumer finance",
        "pembiayaan konsumen",
        "pembiayaan motor",
        "pembiayaan kendaraan",
    ),
    "Sales Management": ("sales management", "manajemen penjualan", "mengelola tim penjualan"),
    "Sales Operations": ("sales operations", "operasional penjualan", "operational sales"),
    "Branch Marketing": ("branch marketing", "marketing cabang", "pemasaran cabang"),
    "Credit Marketing": ("credit marketing", "marketing pembiayaan", "credit marketing officer", "cmo"),
    "Marketing": ("marketing", "pemasaran"),
    "Business Development": ("business development", "pengembangan bisnis", "peluang bisnis baru"),
    "Team Leadership": ("team leadership", "leadership", "kepemimpinan", "memimpin tim"),
    "Team Management": ("team management", "management team", "manajemen tim", "mengelola tim"),
    "Pipeline Management": ("pipeline management", "sales pipeline", "pipeline"),
    "Target Achievement": (
        "target achievement",
        "pencapaian target",
        "mencapai target",
        "target oriented",
        "berorientasi pada target",
    ),
    "Customer Handling": (
        "customer handling",
        "menangani pelanggan",
        "pelayanan pelanggan",
        "customer service",
        "menangani keluhan",
    ),
    "Customer Relationship Management": (
        "customer relationship management",
        "crm",
        "hubungan pelanggan",
        "menjaga hubungan",
        "membina hubungan",
    ),
    "Dealer Relationship": ("dealer relationship", "hubungan dengan dealer", "relasi dengan dealer"),
    "Credit Analysis": ("credit analysis", "analisa kredit", "analisis kredit", "kelayakan kredit"),
    "Collection": ("collection", "penagihan", "koleksi"),
    "Negotiation": ("negotiation", "negosiasi", "bernegosiasi"),
    "Branch Operations": ("branch operations", "operasional cabang", "operational branch"),
    "Stakeholder Management": ("stakeholder management", "stakeholder", "mitra bisnis"),
    "Reporting": ("reporting", "laporan", "pelaporan"),
    "Data Analysis": ("data analysis", "analisis data", "menganalisis data"),
    "Operational Coordination": ("operational coordination", "koordinasi operasional", "berkoordinasi"),
    "Problem Solving": ("problem solving", "pemecahan masalah"),
    "Microsoft Office": ("microsoft office", "ms office", "word", "excel", "powerpoint"),
    "Leadership": ("leadership", "kepemimpinan", "memimpin tim"),
    "Communication": ("communication", "komunikasi", "komunikatif"),
}

ROLE_EQUIVALENTS: dict[str, tuple[str, ...]] = {
    "Sales Supervisor": ("team leader sales", "sales team leader"),
    "Area Sales Supervisor": ("sales supervisor area",),
    "Territory Sales Supervisor": ("territory supervisor", "area sales supervisor"),
    "Credit Marketing Officer": ("cmo", "marketing pembiayaan"),
    "Dealer Relationship Officer": ("dealer relationship", "dealer officer"),
}

PROVINCE_ALIASES: dict[str, tuple[str, ...]] = {
    "dki jakarta": ("dki jakarta", "jakarta"),
    "jawa barat": ("jawa barat", "west java", "jabar"),
    "banten": ("banten",),
    "jawa tengah": ("jawa tengah", "central java", "jateng"),
    "di yogyakarta": ("di yogyakarta", "yogyakarta", "jogja"),
    "jawa timur": ("jawa timur", "east java", "jatim"),
    "bali": ("bali",),
    "sumatera utara": ("sumatera utara", "north sumatra", "sumut"),
    "sumatera barat": ("sumatera barat", "west sumatra", "sumbar"),
    "sumatera selatan": ("sumatera selatan", "south sumatra", "sumsel"),
    "lampung": ("lampung",),
    "riau": ("riau",),
    "kepulauan riau": ("kepulauan riau", "kepri"),
    "kalimantan barat": ("kalimantan barat", "kalbar"),
    "kalimantan timur": ("kalimantan timur", "kaltim"),
    "kalimantan selatan": ("kalimantan selatan", "kalsel"),
    "sulawesi selatan": ("sulawesi selatan", "sulsel"),
    "sulawesi utara": ("sulawesi utara", "sulut"),
}

CITY_TO_PROVINCE: dict[str, str] = {
    # Jabodetabek
    "jakarta": "dki jakarta",
    "jakarta pusat": "dki jakarta",
    "jakarta utara": "dki jakarta",
    "jakarta selatan": "dki jakarta",
    "jakarta barat": "dki jakarta",
    "jakarta timur": "dki jakarta",
    "bogor": "jawa barat",
    "depok": "jawa barat",
    "bekasi": "jawa barat",
    "tangerang": "banten",
    "tangerang selatan": "banten",
    # Jawa Barat
    "bandung": "jawa barat",
    "cimahi": "jawa barat",
    "cianjur": "jawa barat",
    "sukabumi": "jawa barat",
    "karawang": "jawa barat",
    "purwakarta": "jawa barat",
    "subang": "jawa barat",
    "garut": "jawa barat",
    "tasikmalaya": "jawa barat",
    "cirebon": "jawa barat",
    "majalengka": "jawa barat",
    "kuningan": "jawa barat",
    "indramayu": "jawa barat",
    # Banten
    "serang": "banten",
    "cilegon": "banten",
    "lebak": "banten",
    "pandeglang": "banten",
    # Pilot/outside preferred area examples
    "surabaya": "jawa timur",
    "malang": "jawa timur",
    "jember": "jawa timur",
    "sidoarjo": "jawa timur",
    "semarang": "jawa tengah",
    "solo": "jawa tengah",
    "surakarta": "jawa tengah",
    "yogyakarta": "di yogyakarta",
    "denpasar": "bali",
    "medan": "sumatera utara",
    "padang": "sumatera barat",
    "palembang": "sumatera selatan",
    "pekanbaru": "riau",
    "batam": "kepulauan riau",
    "bandar lampung": "lampung",
    "pontianak": "kalimantan barat",
    "balikpapan": "kalimantan timur",
    "samarinda": "kalimantan timur",
    "banjarmasin": "kalimantan selatan",
    "makassar": "sulawesi selatan",
    "manado": "sulawesi utara",
}

JABODETABEK_CITIES = {
    "jakarta",
    "jakarta pusat",
    "jakarta utara",
    "jakarta selatan",
    "jakarta barat",
    "jakarta timur",
    "bogor",
    "depok",
    "tangerang",
    "tangerang selatan",
    "bekasi",
}
REMOTE_ALIASES = ("remote", "work from home", "wfh", "fully remote")
HYBRID_ALIASES = ("hybrid", "hibrida", "work from office and home")


def normalize(text: str) -> str:
    return " ".join(WORD_RE.findall(str(text).lower()))


def phrase_matches(phrase: str, text: str) -> bool:
    normalized_phrase = normalize(phrase)
    normalized_text = normalize(text)
    if not normalized_phrase:
        return False
    if normalized_phrase in normalized_text:
        return True
    stopwords = {"of", "to", "in", "for", "and", "or", "di", "ke", "dan", "atau"}
    tokens = [
        token
        for token in normalized_phrase.split()
        if len(token) > 1 and token not in stopwords
    ]
    return bool(tokens) and all(token in normalized_text.split() for token in tokens)


def analyze_job(job: Job, profile: dict[str, Any], settings: dict[str, Any]) -> AnalysisResult:
    """Analyze with AI when configured, while preserving deterministic safety guardrails."""
    rule_result = analyze_job_rules(job, profile, settings)
    mode = str(settings.get("analysis_mode", "ai_with_fallback")).lower().strip()
    if mode == "rule_only":
        return rule_result
    if mode not in {"ai_with_fallback", "ai_required"}:
        raise ValueError(f"analysis_mode tidak dikenal: {mode}")

    analyzer = OpenAIJobAnalyzer(settings)
    try:
        provider_result = analyzer.analyze(job, profile)
        return merge_ai_with_guardrails(
            job=job,
            profile=profile,
            settings=settings,
            rule_result=rule_result,
            ai_data=provider_result.data,
            provider=provider_result.provider,
            model=provider_result.model,
        )
    except AIAnalysisError as exc:
        if mode == "ai_required":
            raise
        rule_result.analysis_mode = "RULE_FALLBACK"
        rule_result.reasons.append(f"Fallback lokal: {exc}")
        return rule_result


def analyze_job_rules(job: Job, profile: dict[str, Any], settings: dict[str, Any]) -> AnalysisResult:
    title_text = normalize(job.title)
    full_text = normalize(f"{job.title}. {job.description}. {job.location}")
    target_roles = _strings(profile.get("target_roles", []))
    skills = _unique(_strings(profile.get("skills", [])))
    transferable = _unique(_strings(profile.get("transferable_skills", [])))
    locations = _unique(_strings(profile.get("preferred_locations", [])))
    exclusions = _strings(profile.get("excluded_role_keywords", []))

    matched_roles = [role for role in target_roles if role_matches(role, job.title)]
    matched_skills = [skill for skill in skills if skill_matches(skill, full_text)]
    matched_transferable = [item for item in transferable if skill_matches(item, full_text)]
    location_score, matched_locations, location_reason = match_location(job, locations)

    required, preferred = extract_requirements(job.description)
    skill_catalog = _unique(skills + _strings(profile.get("skill_catalog", [])))
    required_skills = [
        skill for skill in skill_catalog if any(skill_matches(skill, item) for item in required)
    ]
    candidate_competencies = _unique(skills + transferable)
    missing_required_skills = [
        skill for skill in required_skills if not candidate_has_competency(skill, candidate_competencies)
    ]
    matched_required_skills = [
        skill for skill in required_skills if candidate_has_competency(skill, candidate_competencies)
    ]

    years_required = extract_years_required(job.description)
    seniority = infer_seniority(job.title, years_required)
    career_level = str(profile.get("career_level", "OFFICER_TO_SUPERVISOR")).upper().strip()
    target_years = _int(profile.get("years_experience_target_domain"), 3)
    max_years = _int(profile.get("max_years_required"), 5)

    role_tokens: set[str] = set()
    for role in target_roles:
        role_tokens.update(token for token in normalize(role).split() if len(token) > 3)
    title_tokens = set(title_text.split())
    role_overlap = len(role_tokens & title_tokens) / max(1, len(title_tokens))

    role_score = 35 if matched_roles else min(28, round(role_overlap * 35))
    skill_score = min(35, round((len(matched_skills) / max(1, min(8, len(skills)))) * 35))
    transferable_score = min(10, len(matched_transferable) * 2)
    level_score, level_flags = score_level_fit(
        seniority=seniority,
        years_required=years_required,
        career_level=career_level,
        target_years=target_years,
        max_years=max_years,
    )

    red_flags: list[str] = list(level_flags)
    excluded_matches = [item for item in exclusions if phrase_matches(item, job.title)]
    if excluded_matches:
        red_flags.append("Role di luar target: " + ", ".join(excluded_matches))
    if missing_required_skills:
        red_flags.append("Skill wajib belum ada: " + ", ".join(missing_required_skills))
    for marker in SCAM_MARKERS:
        if marker in full_text:
            red_flags.append(f"Indikasi lowongan mencurigakan: {marker}")

    score = role_score + skill_score + location_score + transferable_score + level_score
    score -= min(30, 10 * len(missing_required_skills))
    score -= 30 if any("mencurigakan" in item for item in red_flags) else 0
    score = _clamp(score)

    decision = decision_from_score(score, settings)
    decision = apply_hard_guardrails(
        decision=decision,
        score=score,
        seniority=seniority,
        years_required=years_required,
        max_years=max_years,
        career_level=career_level,
        missing_required=missing_required_skills,
        red_flags=red_flags,
        matched_roles=matched_roles,
    )

    reasons = [
        f"Profil aktif: {career_level}; pengalaman domain {target_years} tahun; batas persyaratan {max_years} tahun",
        f"Kecocokan role: {role_score}/35",
        f"Kecocokan skill: {skill_score}/35",
        f"Kecocokan lokasi: {location_score}/10 ({location_reason})",
        f"Transferable skill: {transferable_score}/10",
        f"Kesesuaian level: {level_score}/10 ({seniority})",
    ]
    if matched_locations:
        reasons.append("Lokasi cocok: " + ", ".join(matched_locations))
    if matched_skills:
        reasons.append("Skill cocok: " + ", ".join(matched_skills[:10]))
    if matched_transferable:
        reasons.append("Kekuatan transferable: " + ", ".join(matched_transferable[:6]))
    if not matched_roles:
        reasons.append("Judul role belum cocok kuat dengan target utama")
    if red_flags:
        reasons.extend(red_flags)

    summary = _build_rule_summary(job, score, decision, matched_skills, red_flags)
    return AnalysisResult(
        score=score,
        decision=decision,
        analysis_mode="RULE_ONLY",
        provider="local",
        confidence=70 if job.description.strip() else 35,
        summary=summary,
        seniority_level=seniority,
        estimated_years_required=years_required,
        matched_roles=matched_roles,
        required_requirements=required,
        preferred_requirements=preferred,
        matched_required=matched_required_skills,
        missing_required=missing_required_skills,
        matched_skills=matched_skills,
        missing_skills=missing_required_skills,
        transferable_strengths=matched_transferable,
        red_flags=_unique(red_flags),
        reasons=_unique(reasons),
    )


def merge_ai_with_guardrails(
    job: Job,
    profile: dict[str, Any],
    settings: dict[str, Any],
    rule_result: AnalysisResult,
    ai_data: dict[str, Any],
    provider: str,
    model: str,
) -> AnalysisResult:
    ai_score = _clamp(_int(ai_data.get("score"), rule_result.score))
    score = _clamp(round(ai_score * 0.7 + rule_result.score * 0.3))
    seniority = _enum_text(ai_data.get("seniority_level"), rule_result.seniority_level)
    years_required = max(
        rule_result.estimated_years_required,
        _int(ai_data.get("estimated_years_required"), 0),
    )
    max_years = _int(profile.get("max_years_required"), 5)
    career_level = str(profile.get("career_level", "OFFICER_TO_SUPERVISOR")).upper().strip()

    matched_roles = _unique(_strings(ai_data.get("matched_roles", [])) + rule_result.matched_roles)
    required = _unique(_strings(ai_data.get("required_requirements", [])) + rule_result.required_requirements)
    preferred = _unique(_strings(ai_data.get("preferred_requirements", [])) + rule_result.preferred_requirements)
    matched_required = _unique(_strings(ai_data.get("matched_required", [])) + rule_result.matched_required)
    missing_required = _unique(_strings(ai_data.get("missing_required", [])) + rule_result.missing_required)
    matched_skills = _unique(_strings(ai_data.get("matched_skills", [])) + rule_result.matched_skills)
    missing_skills = _unique(_strings(ai_data.get("missing_skills", [])) + rule_result.missing_skills)
    transferable = _unique(
        _strings(ai_data.get("transferable_strengths", [])) + rule_result.transferable_strengths
    )
    red_flags = _unique(_strings(ai_data.get("red_flags", [])) + rule_result.red_flags)
    reasons = _unique(_strings(ai_data.get("reasons", [])) + rule_result.reasons)

    decision = decision_from_score(score, settings)
    decision = apply_hard_guardrails(
        decision=decision,
        score=score,
        seniority=seniority,
        years_required=years_required,
        max_years=max_years,
        career_level=career_level,
        missing_required=missing_required,
        red_flags=red_flags,
        matched_roles=matched_roles,
    )
    ai_recommendation = str(ai_data.get("recommended_action", "")).upper()
    if ai_recommendation == "SKIP":
        decision = "SKIP"
    elif ai_recommendation == "REVIEW" and decision == "APPLY":
        decision = "REVIEW"
    reasons.insert(0, f"AI recommendation: {ai_recommendation or '-'}; final guardrail: {decision}")

    return AnalysisResult(
        score=score,
        decision=decision,
        analysis_mode="AI",
        provider=provider,
        model=model,
        confidence=_clamp(_int(ai_data.get("confidence"), 70)),
        summary=str(ai_data.get("summary", "")).strip() or rule_result.summary,
        seniority_level=seniority,
        estimated_years_required=years_required,
        matched_roles=matched_roles,
        required_requirements=required,
        preferred_requirements=preferred,
        matched_required=matched_required,
        missing_required=missing_required,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        transferable_strengths=transferable,
        red_flags=red_flags,
        reasons=reasons,
    )


def extract_requirements(description: str) -> tuple[list[str], list[str]]:
    required: list[str] = []
    preferred: list[str] = []
    for sentence in SENTENCE_RE.split(description.replace("•", ". ").replace("- ", ". ")):
        clean = " ".join(sentence.split()).strip(" .:-")
        if len(clean) < 5:
            continue
        lower = clean.lower()
        if any(marker in lower for marker in PREFERRED_MARKERS):
            preferred.append(clean)
        elif any(marker in lower for marker in REQUIRED_MARKERS) or extract_years_required(clean):
            required.append(clean)
    return _unique(required)[:20], _unique(preferred)[:20]


def extract_years_required(text: str) -> int:
    """Extract only years directly connected to work-experience wording.

    Age limits such as "maksimal 35 tahun", "usia 33 tahun", or
    "maximum age 28 years" are deliberately ignored.
    """
    values: list[int] = []
    lowered = str(text).lower()
    for match in YEAR_TOKEN_RE.finditer(lowered):
        value = int(match.group(2) or match.group(1))
        start, end = match.span()
        before = lowered[max(0, start - 100) : start]
        after = lowered[end : min(len(lowered), end + 70)]
        local_before = before[-35:]
        local_after = after[:25]

        # Immediate age wording always wins for this number. Use word boundaries so
        # the English marker "age" does not accidentally match words like "manager".
        age_context = f"{local_before} {local_after}"
        if re.search(
            r"\b(?:usia|umur|age)\b|maksimal\s+usia|usia\s+maksimal|maximum\s+age",
            age_context,
            re.I,
        ):
            continue

        exp_before = min(
            (len(before) - before.rfind(marker) for marker in EXPERIENCE_MARKERS if marker in before),
            default=10_000,
        )
        exp_after = min(
            (after.find(marker) for marker in EXPERIENCE_MARKERS if marker in after),
            default=10_000,
        )
        if exp_before <= 85 or exp_after <= 35:
            values.append(value)
    return max(values, default=0)


def infer_seniority(text: str, years_required: int = 0) -> str:
    normalized = normalize(text)

    # Account/relationship manager titles are commonly individual-contributor roles.
    if phrase_matches("account manager", normalized) or phrase_matches("relationship manager", normalized):
        return "MID"

    for level in (
        "INTERNSHIP",
        "SUPERVISOR",
        "MANAGER",
        "LEAD",
        "SENIOR",
        "JUNIOR",
        "ENTRY",
        "MID",
    ):
        if any(phrase_matches(keyword, normalized) for keyword in SENIORITY_KEYWORDS[level]):
            return level
    if years_required >= 7:
        return "SENIOR"
    if years_required >= 3:
        return "MID"
    if years_required in {1, 2}:
        return "JUNIOR"
    return "UNKNOWN"


def decision_from_score(score: int, settings: dict[str, Any]) -> str:
    apply_threshold = int(settings.get("apply_threshold", 65))
    review_threshold = int(settings.get("review_threshold", 45))
    if score >= apply_threshold:
        return "APPLY"
    if score >= review_threshold:
        return "REVIEW"
    return "SKIP"


def apply_hard_guardrails(
    decision: str,
    score: int,
    seniority: str,
    years_required: int,
    max_years: int,
    career_level: str,
    missing_required: list[str],
    red_flags: list[str],
    matched_roles: list[str],
) -> str:
    if any("mencurigakan" in normalize(flag) for flag in red_flags):
        return "SKIP"
    if years_required >= max(8, max_years + 3):
        return "SKIP"
    if years_required > max_years:
        return "REVIEW" if score >= 55 and matched_roles else "SKIP"

    # OFFICER_TO_SUPERVISOR explicitly accepts supervisor and team-lead roles.
    if career_level == "OFFICER_TO_SUPERVISOR" and seniority in {"MANAGER", "SENIOR"}:
        if decision == "APPLY":
            return "REVIEW"
    if len(missing_required) >= 3:
        return "SKIP" if score < 70 else "REVIEW"
    if missing_required and decision == "APPLY":
        return "REVIEW"
    return decision


def score_level_fit(
    seniority: str,
    years_required: int,
    career_level: str,
    target_years: int,
    max_years: int,
) -> tuple[int, list[str]]:
    flags: list[str] = []
    if career_level == "OFFICER_TO_SUPERVISOR":
        score_by_level = {
            "INTERNSHIP": 4,
            "ENTRY": 8,
            "JUNIOR": 9,
            "MID": 10,
            "SUPERVISOR": 10,
            "LEAD": 9,
            "UNKNOWN": 7,
            "SENIOR": 4,
            "MANAGER": 2,
        }
    else:
        score_by_level = {
            "INTERNSHIP": 8,
            "ENTRY": 10,
            "JUNIOR": 10,
            "MID": 6,
            "SUPERVISOR": 3,
            "LEAD": 2,
            "UNKNOWN": 6,
            "SENIOR": 0,
            "MANAGER": 0,
        }

    level_score = score_by_level.get(seniority, 6)
    if seniority in {"MANAGER", "SENIOR"} and career_level == "OFFICER_TO_SUPERVISOR":
        flags.append(f"Level lowongan {seniority} berada di atas target {career_level}")
    if years_required > max_years:
        level_score = min(level_score, 2)
        flags.append(
            f"Meminta sekitar {years_required} tahun pengalaman; batas target profil {max_years} tahun"
        )
    elif years_required and years_required <= max_years:
        gap = abs(years_required - target_years)
        if gap <= 1:
            level_score = min(10, level_score + 1)
    return level_score, flags


def role_matches(role: str, title: str) -> bool:
    if phrase_matches(role, title):
        return True
    aliases = ROLE_EQUIVALENTS.get(role, ())
    return any(phrase_matches(alias, title) for alias in aliases)


def skill_matches(skill: str, text: str) -> bool:
    aliases = SKILL_ALIASES.get(skill, (skill,))
    return any(phrase_matches(alias, text) for alias in aliases)


def candidate_has_competency(required_skill: str, competencies: list[str]) -> bool:
    for competency in competencies:
        if normalize(required_skill) == normalize(competency):
            return True
        if skill_matches(required_skill, competency) or skill_matches(competency, required_skill):
            return True
    return False


def match_location(job: Job, preferred_locations: list[str]) -> tuple[int, list[str], str]:
    location_text = normalize(job.location)
    work_mode_text = normalize(f"{job.title} {job.location} {job.description}")
    preferred_norm = {normalize(item): item for item in preferred_locations if normalize(item)}
    matched: list[str] = []

    remote_job = job.remote or any(phrase_matches(alias, work_mode_text) for alias in REMOTE_ALIASES)
    hybrid_job = any(phrase_matches(alias, work_mode_text) for alias in HYBRID_ALIASES)
    if remote_job and "remote" in preferred_norm:
        matched.append(preferred_norm["remote"])
    if hybrid_job and "hybrid" in preferred_norm:
        matched.append(preferred_norm["hybrid"])
    if matched:
        return 10, _unique(matched), "mode kerja pilihan"

    # Direct city/province/Jabodetabek match, excluding broad country fallback.
    for norm, original in preferred_norm.items():
        if norm in {"remote", "hybrid", "indonesia"}:
            continue
        if phrase_matches(norm, location_text):
            matched.append(original)
    if matched:
        return 10, _unique(matched), "lokasi pilihan langsung"

    job_cities = {city for city in CITY_TO_PROVINCE if phrase_matches(city, location_text)}
    job_provinces = {
        province
        for province, aliases in PROVINCE_ALIASES.items()
        if any(phrase_matches(alias, location_text) for alias in aliases)
    }
    job_provinces.update(CITY_TO_PROVINCE[city] for city in job_cities)

    preferred_provinces = {
        province
        for province, aliases in PROVINCE_ALIASES.items()
        if any(any(phrase_matches(alias, pref) for alias in aliases) for pref in preferred_norm)
    }
    province_matches = job_provinces & preferred_provinces
    if province_matches:
        labels = [preferred_norm.get(province, province.title()) for province in sorted(province_matches)]
        return 10, _unique(labels), "kota/provinsi pilihan"

    prefers_jabodetabek = "jabodetabek" in preferred_norm
    is_jabodetabek = phrase_matches("jabodetabek", location_text) or bool(job_cities & JABODETABEK_CITIES)
    if prefers_jabodetabek and is_jabodetabek:
        return 10, [preferred_norm["jabodetabek"]], "wilayah Jabodetabek"

    recognized_indonesia = bool(job_cities or job_provinces) or phrase_matches("indonesia", location_text)
    if "indonesia" in preferred_norm and recognized_indonesia:
        if phrase_matches("indonesia", location_text):
            return 7, [preferred_norm["indonesia"]], "lokasi nasional"
        return 4, [preferred_norm["indonesia"]], "di Indonesia tetapi di luar area utama"

    return 0, [], "di luar lokasi pilihan"


def _build_rule_summary(
    job: Job,
    score: int,
    decision: str,
    matched_skills: list[str],
    red_flags: list[str],
) -> str:
    skill_text = ", ".join(matched_skills[:5]) or "belum ada skill yang terdeteksi kuat"
    risk_text = "; ".join(red_flags[:2]) if red_flags else "tidak ada red flag utama yang terdeteksi"
    return (
        f"{job.title} di {job.company} mendapat skor {score}/100 dan keputusan {decision}. "
        f"Kecocokan utama: {skill_text}. Catatan risiko: {risk_text}."
    )


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = " ".join(str(value).split()).strip()
        key = normalize(clean)
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def _clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _enum_text(value: Any, default: str) -> str:
    allowed = {
        "INTERNSHIP",
        "ENTRY",
        "JUNIOR",
        "MID",
        "SUPERVISOR",
        "SENIOR",
        "LEAD",
        "MANAGER",
        "UNKNOWN",
    }
    text = str(value or "").upper()
    return text if text in allowed else default
