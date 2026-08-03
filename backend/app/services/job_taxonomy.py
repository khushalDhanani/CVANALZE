# backend/app/services/job_taxonomy.py
import functools
import logging
import re
import threading
import time
from typing import Any

from pydantic import BaseModel, Field

from app.core.rule_config_manager import RuleConfigManager
from app.services.dynamic_taxonomy_service import DynamicTaxonomyService

logger = logging.getLogger("cv_analyzer")


class VacancyDTO(BaseModel):
    """Strongly-typed DTO representing a job opening for taxonomy classification."""

    id: str = ""
    title: str = ""
    title_lower: str = ""
    department: str = ""
    department_lower: str = ""
    description: str = ""
    normalized_description: str = ""
    required_skills: list[str] = Field(default_factory=list)
    normalized_required_skills: str = ""
    normalized_job_text: str = ""
    raw_job: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_job(cls, job: Any) -> "VacancyDTO":
        """Constructs a VacancyDTO from a raw dict or JobEvaluationContext without redundant lowercasing."""
        if isinstance(job, cls):
            return job

        # Check for JobEvaluationContext-like objects
        if hasattr(job, "title_lower") and hasattr(job, "department_lower"):
            title = str(getattr(job, "title", "") or "")
            title_lower = str(getattr(job, "title_lower", "") or title.lower())
            dept = str(getattr(job, "department", "") or "")
            dept_lower = str(getattr(job, "department_lower", "") or dept.lower())
            job_id = str(getattr(job, "job_id", "") or "")
            req_skills = list(getattr(job, "required_skills", []) or [])
            req_skills_str = " ".join(str(s).lower() for s in req_skills) if req_skills else ""
            desc = str(getattr(job, "description", "") or "").lower()
            norm_job_text = getattr(job, "normalized_job_text", None) or f"{title_lower} {dept_lower} {desc} {req_skills_str}"
            return cls(
                id=job_id,
                title=title,
                title_lower=title_lower,
                department=dept,
                department_lower=dept_lower,
                description=desc,
                normalized_description=desc,
                required_skills=req_skills,
                normalized_required_skills=req_skills_str,
                normalized_job_text=norm_job_text,
            )

        if isinstance(job, dict):
            job_id = str(job.get("id") or job.get("vacancy_id") or "")
            title = str(job.get("title") or "")
            title_lower = title.strip().lower()
            dept = str(job.get("department_name") or job.get("department") or "")
            dept_lower = dept.strip().lower()
            desc = str(job.get("job_description") or job.get("description") or "").lower()
            req_skills = list(job.get("required_skills") or [])
            req_skills_str = " ".join(str(s).lower() for s in req_skills)
            norm_job_text = str(job.get("normalized_job_text") or f"{title_lower} {dept_lower} {desc} {req_skills_str}")
            return cls(
                id=job_id,
                title=title,
                title_lower=title_lower,
                department=dept,
                department_lower=dept_lower,
                description=desc,
                normalized_description=desc,
                required_skills=req_skills,
                normalized_required_skills=req_skills_str,
                normalized_job_text=norm_job_text,
                raw_job=job,
            )

        raise TypeError(f"Cannot construct VacancyDTO from unsupported type: {type(job)}")


class CandidateResumeDTO(BaseModel):
    """Strongly-typed DTO representing candidate resume input for taxonomy classification."""

    cv_text: str = ""
    summary: str = ""
    experience_titles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    normalized_full_text: str = ""

    @classmethod
    def from_resume(cls, cv_text: str, resume_json: dict[str, Any] | None = None) -> "CandidateResumeDTO":
        text_lower = cv_text.lower()
        summary = ""
        exp_titles: list[str] = []
        skills_str: list[str] = []
        edu_str: list[str] = []

        if resume_json and isinstance(resume_json, dict):
            summary = str(resume_json.get("summary") or "").lower()
            exp_list = resume_json.get("experience", [])
            if isinstance(exp_list, list):
                exp_titles = [str(e.get("title") or "").lower() for e in exp_list if isinstance(e, dict)]
            skills_data = resume_json.get("skills")
            if isinstance(skills_data, (list, dict)):
                skills_str = [str(s).lower() for s in skills_data]
            edu_list = resume_json.get("education", [])
            if isinstance(edu_list, list):
                edu_str = [str(e).lower() for e in edu_list]

        combined = f"{text_lower} {summary} {' '.join(exp_titles)} {' '.join(skills_str)} {' '.join(edu_str)}"
        norm_full_text = re.sub(r"\s+", " ", combined).strip()

        return cls(
            cv_text=cv_text,
            summary=summary,
            experience_titles=exp_titles,
            skills=skills_str,
            education=edu_str,
            normalized_full_text=norm_full_text,
        )


class TaxonomyClassification(BaseModel):
    """Strongly-typed classification result with optional diagnostic telemetry."""

    domain: str
    job_family: str
    compatible_families: tuple[str, ...] = ()
    matched_rule: str | None = None
    matched_branch: int | None = None
    matched_keywords: tuple[str, ...] = ()


class classproperty:
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        return self.func(owner)


class JobTaxonomy:
    """
    4-Tier Enterprise Job Taxonomy: Department -> Domain -> Job Family -> Vacancy.
    Canonical domain/family identifiers below stay consistent with rule_config.json.
    """

    # Canonical Domains
    DOMAIN_IT_SOFTWARE = "IT & Software Services"
    DOMAIN_PLANT_OPERATIONS = "Plant Operations & Maintenance"
    DOMAIN_QUALITY_LAB = "Quality Assurance & QC Laboratory"
    DOMAIN_EHS_ENVIRONMENT = "Environmental Health & Safety (EHS)"
    DOMAIN_PROCESS_PROJECT = "Process & Project Engineering"
    DOMAIN_FINANCE_ADMIN = "Finance & Administration"
    DOMAIN_OTHER = "General Operations"

    # Canonical Job Families
    FAMILY_SOFTWARE_DEV = "Software Engineering & Development"
    FAMILY_IT_NETWORKING_AV = "IT Infrastructure, Networking & AV Systems"
    FAMILY_PLANT_ELECTRICAL = "Plant Electrical & Utility Maintenance"
    FAMILY_CONTROL_INSTRUMENTATION = "Control & Instrumentation (C&I)"
    FAMILY_QC_LAB = "Quality Control (QC) & Laboratory"
    FAMILY_QA_ASSURANCE = "Quality Assurance (QA)"
    FAMILY_FIRE_SAFETY = "Fire, Safety & EHS"
    FAMILY_PROCESS_PROJECT = "Process & Project Engineering"
    FAMILY_ENVIRONMENT_ETP = "Environment & ETP Operations"
    FAMILY_FINANCE_ADMIN = "Finance & Administration"
    FAMILY_OTHER = "General Professional"

    @classproperty
    def COMPATIBILITY_MAP(cls) -> dict[str, set[str]]:
        return {
            family: set(compatible)
            for family, compatible in RuleConfigManager.get_taxonomy_rules().compatibility_map.items()
        }

    @classproperty
    def REVERSE_COMPATIBILITY_MAP(cls) -> dict[str, set[str]]:
        """Precomputed reverse compatibility map: job_family -> set of compatible candidate_families."""
        reverse_map: dict[str, set[str]] = {}
        for cand_fam, job_fams in cls.COMPATIBILITY_MAP.items():
            for job_fam in job_fams:
                reverse_map.setdefault(job_fam, set()).add(cand_fam)
        return reverse_map

    @classmethod
    def validate_taxonomy_config(cls) -> None:
        """
        Validates taxonomy configuration during startup.
        Ensures:
          1. Every family in compatibility_map exists in canonical_families.
          2. Every rule domain exists in canonical_domains.
          3. Every rule family exists in canonical_families.
          4. Zero orphan or unknown domains/families.
        """
        rules = RuleConfigManager.get_taxonomy_rules()
        canonical_domains = set(rules.canonical_domains)
        canonical_families = set(rules.canonical_families)

        if not canonical_domains:
            raise ValueError("[TAXONOMY_VALIDATION_FAILURE] canonical_domains must not be empty")
        if not canonical_families:
            raise ValueError("[TAXONOMY_VALIDATION_FAILURE] canonical_families must not be empty")

        for cand_fam, compatible in rules.compatibility_map.items():
            if cand_fam not in canonical_families:
                raise ValueError(f"[TAXONOMY_VALIDATION_FAILURE] Unknown candidate family in compatibility_map: '{cand_fam}'")
            for job_fam in compatible:
                if job_fam not in canonical_families:
                    raise ValueError(f"[TAXONOMY_VALIDATION_FAILURE] Unknown job family in compatibility_map for '{cand_fam}': '{job_fam}'")

        for r in rules.vacancy_rules:
            if r.domain not in canonical_domains:
                raise ValueError(f"[TAXONOMY_VALIDATION_FAILURE] Vacancy rule '{r.name}' has unknown domain: '{r.domain}'")
            if r.family not in canonical_families:
                raise ValueError(f"[TAXONOMY_VALIDATION_FAILURE] Vacancy rule '{r.name}' has unknown family: '{r.family}'")

        for r in rules.candidate_rules:
            if r.domain not in canonical_domains:
                raise ValueError(f"[TAXONOMY_VALIDATION_FAILURE] Candidate rule '{r.name}' has unknown domain: '{r.domain}'")
            for f in r.families:
                if f not in canonical_families:
                    raise ValueError(f"[TAXONOMY_VALIDATION_FAILURE] Candidate rule '{r.name}' has unknown family: '{f}'")


class TaxonomyMetrics:
    """Thread-safe telemetry metrics counter for TaxonomyClassifier operations."""

    _lock = threading.RLock()
    taxonomy_hits: int = 0
    taxonomy_cache_hits: int = 0
    taxonomy_cache_misses: int = 0
    classification_time_total_ms: float = 0.0

    @classmethod
    def record_hit(cls, cache_hit: bool, duration_ms: float) -> None:
        with cls._lock:
            cls.taxonomy_hits += 1
            if cache_hit:
                cls.taxonomy_cache_hits += 1
            else:
                cls.taxonomy_cache_misses += 1
            cls.classification_time_total_ms += duration_ms

    @classmethod
    def get_metrics(cls) -> dict[str, Any]:
        with cls._lock:
            avg_ms = (
                round(cls.classification_time_total_ms / cls.taxonomy_hits, 4)
                if cls.taxonomy_hits > 0
                else 0.0
            )
            return {
                "taxonomy_hits": cls.taxonomy_hits,
                "taxonomy_cache_hits": cls.taxonomy_cache_hits,
                "taxonomy_cache_misses": cls.taxonomy_cache_misses,
                "classification_time_total_ms": round(cls.classification_time_total_ms, 2),
                "average_classification_time_ms": avg_ms,
            }


class TaxonomyClassifier:
    """
    Classifier for categorizing vacancies and candidate CVs into the 4-Tier Job Taxonomy.
    Optimized for zero runtime regex compilation, zero repeated lowercasing, fast token-set
    intersection keyword matching, dual LRU caching, and strong typing via DTOs.
    """

    @staticmethod
    def _condition_matches(condition: Any, scopes: dict[str, str], scope_tokens: dict[str, set[str]]) -> tuple[bool, tuple[str, ...]]:
        text = scopes.get(condition.scope, "")
        tokens = scope_tokens.get(condition.scope, set())

        if not condition.keywords:
            return (False, ())

        matched_kws: list[str] = []

        if condition.mode == "any":
            # Fast single-word token intersection check
            for k in condition.keywords:
                k_norm = k.lower().strip()
                if " " in k_norm or "-" in k_norm:
                    if k_norm in text:
                        matched_kws.append(k_norm)
                elif k_norm in tokens or k_norm in text:
                    matched_kws.append(k_norm)
            is_match = len(matched_kws) > 0
        else:  # mode == "all"
            is_match = True
            for k in condition.keywords:
                k_norm = k.lower().strip()
                if " " in k_norm or "-" in k_norm:
                    if k_norm not in text:
                        is_match = False
                        break
                elif k_norm not in tokens and k_norm not in text:
                    is_match = False
                    break
                else:
                    matched_kws.append(k_norm)

        final_match = not is_match if condition.negate else is_match
        return (final_match, tuple(matched_kws) if is_match else ())

    @staticmethod
    def _branch_matches(branch: Any, scopes: dict[str, str], scope_tokens: dict[str, set[str]]) -> tuple[bool, tuple[str, ...]]:
        branch_kws: list[str] = []
        for c in branch.conditions:
            matches, kws = TaxonomyClassifier._condition_matches(c, scopes, scope_tokens)
            if not matches:
                return (False, ())
            branch_kws.extend(kws)
        return (True, tuple(branch_kws))

    @staticmethod
    def _rule_matches(rule: Any, scopes: dict[str, str], scope_tokens: dict[str, set[str]]) -> tuple[bool, int | None, tuple[str, ...]]:
        for branch_idx, b in enumerate(rule.branches):
            matches, kws = TaxonomyClassifier._branch_matches(b, scopes, scope_tokens)
            if matches:
                return (True, branch_idx, kws)
        return (False, None, ())

    @staticmethod
    @functools.lru_cache(maxsize=1024)
    def _classify_vacancy_cached(normalized_job_text: str, title_lower: str, dept_lower: str) -> tuple[str, str, str | None, int | None, tuple[str, ...]]:
        """
        Classifies vacancy into (domain, family, rule_name, branch_idx, matched_keywords).
        Thread-safe under CPython GIL atomic LRU cache operations.
        """
        scopes = {"title": title_lower, "dept": dept_lower, "full_text": normalized_job_text}
        scope_tokens = {
            "title": set(re.findall(r"\w+", title_lower)),
            "dept": set(re.findall(r"\w+", dept_lower)),
            "full_text": set(re.findall(r"\w+", normalized_job_text)),
        }
        taxonomy = RuleConfigManager.get_taxonomy_rules()

        for rule in taxonomy.vacancy_rules:
            matches, branch_idx, kws = TaxonomyClassifier._rule_matches(rule, scopes, scope_tokens)
            if matches:
                return (rule.domain, rule.family, rule.name, branch_idx, kws)

        return (taxonomy.default_domain, taxonomy.default_family, None, None, ())

    @staticmethod
    @functools.lru_cache(maxsize=512)
    def classify_candidate_by_full_text(candidate_full_text: str) -> tuple[str, tuple[str, ...]]:
        """
        Classifies candidate full text into (domain, families_tuple).
        Cached via functools.lru_cache(maxsize=512). Thread-safe under CPython GIL.
        """
        scopes = {"full_text": candidate_full_text}
        scope_tokens = {"full_text": set(re.findall(r"\w+", candidate_full_text))}
        taxonomy = RuleConfigManager.get_taxonomy_rules()

        for rule in taxonomy.candidate_rules:
            matches, _, _ = TaxonomyClassifier._rule_matches(rule, scopes, scope_tokens)
            if matches:
                return (rule.domain, tuple(rule.families))

        return (taxonomy.default_domain, (taxonomy.default_family,))

    @classmethod
    def classify_vacancy_dto(cls, dto: VacancyDTO) -> TaxonomyClassification:
        """Strongly-typed classification of VacancyDTO returning TaxonomyClassification via DynamicTaxonomyService."""
        t0 = time.perf_counter()

        # 1. Try Dynamic Vector & MSSQL taxonomy resolution first
        dyn_res = DynamicTaxonomyService.resolve_vacancy_domain_and_family(
            title=dto.title,
            department=dto.department,
            description=dto.description,
            required_skills=dto.required_skills,
        )

        if dyn_res.match_source != "legacy_fallback":
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
            return TaxonomyClassification(
                domain=dyn_res.domain_name,
                job_family=dyn_res.family_name,
                compatible_families=tuple(JobTaxonomy.REVERSE_COMPATIBILITY_MAP.get(dyn_res.family_name, {dyn_res.family_name})),
                matched_rule=f"dynamic:{dyn_res.match_source}",
                matched_branch=0,
                matched_keywords=(dyn_res.matched_term,) if dyn_res.matched_term else (),
            )

        # 2. Fallback to static rule classification
        cache_info_before = cls._classify_vacancy_cached.cache_info()
        domain, family, rule_name, branch_idx, kws = cls._classify_vacancy_cached(
            dto.normalized_job_text, dto.title_lower, dto.department_lower
        )
        cache_info_after = cls._classify_vacancy_cached.cache_info()
        cache_hit = cache_info_after.hits > cache_info_before.hits
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        TaxonomyMetrics.record_hit(cache_hit, elapsed_ms)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"[TAXONOMY_VACANCY] Title='{dto.title}' -> Domain='{domain}', Family='{family}' | "
                f"Rule='{rule_name}', Branch={branch_idx}, Keywords={kws}, CacheHit={cache_hit}"
            )

        return TaxonomyClassification(
            domain=domain,
            job_family=family,
            compatible_families=tuple(JobTaxonomy.REVERSE_COMPATIBILITY_MAP.get(family, {family})),
            matched_rule=rule_name,
            matched_branch=branch_idx,
            matched_keywords=kws,
        )

    @classmethod
    def classify_vacancy(cls, job: dict[str, Any] | VacancyDTO | Any) -> tuple[str, str]:
        """
        Classifies a job opening into (domain, job_family).
        Accepts VacancyDTO, JobEvaluationContext, or raw dicts.
        Preserves 100% backward compatibility.
        """
        dto = VacancyDTO.from_job(job)
        classification = cls.classify_vacancy_dto(dto)
        return (classification.domain, classification.job_family)

    @classmethod
    def classify_candidate_dto(cls, dto: CandidateResumeDTO) -> TaxonomyClassification:
        """Strongly-typed classification of CandidateResumeDTO returning TaxonomyClassification via DynamicTaxonomyService."""
        t0 = time.perf_counter()

        # 1. Try Dynamic Vector & MSSQL taxonomy resolution first
        role_text = " ".join(dto.experience_titles) if dto.experience_titles else dto.summary
        dyn_res = DynamicTaxonomyService.resolve_candidate_role_and_domain(
            role_or_summary=role_text or dto.normalized_full_text,
            skills=dto.skills,
        )

        if dyn_res.match_source != "legacy_fallback":
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
            return TaxonomyClassification(
                domain=dyn_res.domain_name,
                job_family=dyn_res.family_name,
                compatible_families=(dyn_res.family_name,),
                matched_rule=f"dynamic:{dyn_res.match_source}",
            )

        # 2. Fallback to static rule classification
        cache_info_before = cls.classify_candidate_by_full_text.cache_info()
        domain, families_tuple = cls.classify_candidate_by_full_text(
            dto.normalized_full_text
        )
        cache_info_after = cls.classify_candidate_by_full_text.cache_info()
        cache_hit = cache_info_after.hits > cache_info_before.hits
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        TaxonomyMetrics.record_hit(cache_hit, elapsed_ms)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"[TAXONOMY_CANDIDATE] Domain='{domain}', Families={families_tuple} | CacheHit={cache_hit}"
            )

        return TaxonomyClassification(
            domain=domain,
            job_family=families_tuple[0] if families_tuple else JobTaxonomy.FAMILY_OTHER,
            compatible_families=families_tuple,
        )

    @classmethod
    def classify_candidate(cls, cv_text: str, resume_json: dict[str, Any] | None = None) -> tuple[str, list[str]]:
        """
        Classifies candidate CV text into primary domain and list of compatible job families.
        Cached once per candidate_full_text string.
        Preserves 100% backward compatibility.
        """
        dto = CandidateResumeDTO.from_resume(cv_text, resume_json=resume_json)
        classification = cls.classify_candidate_dto(dto)
        return (classification.domain, list(classification.compatible_families))

    @classmethod
    def are_families_compatible(cls, candidate_families: list[str], job_family: str) -> bool:
        """
        Returns True if candidate_families contains or is compatible with job_family via DynamicTaxonomyService or legacy config map.
        Preserves 100% backward compatibility.
        """
        for cand_fam in candidate_families:
            if cand_fam == job_family:
                return True
            is_compat, score = DynamicTaxonomyService.check_family_compatibility(cand_fam, job_family)
            if is_compat and score > 0.4:
                return True
        return False

    @classmethod
    def get_metrics(cls) -> dict[str, Any]:
        """Exposes telemetry diagnostics and metrics for TaxonomyClassifier operations."""
        return TaxonomyMetrics.get_metrics()
