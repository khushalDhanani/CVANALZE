from __future__ import annotations
# backend/app/services/job_taxonomy.py
import logging
import re
import threading
import time
from typing import Any

from pydantic import BaseModel, Field

from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
from app.schemas.classification_types import MatchStatus

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
            exp_list = resume_json.get("work_experience", []) or resume_json.get("experience", [])
            if isinstance(exp_list, list):
                exp_titles = [str(e.get("job_title") or e.get("title") or "").lower() for e in exp_list if isinstance(e, dict)]
            
            projects_list = resume_json.get("projects", [])
            if isinstance(projects_list, list):
                exp_titles.extend([str(p.get("title") or p.get("project_name") or "").lower() for p in projects_list if isinstance(p, dict)])
            
            skills_data = resume_json.get("skills")
            if isinstance(skills_data, dict):
                if "all_skills" in skills_data:
                    skills_str = [str(s).lower() for s in skills_data["all_skills"]]
                elif "categorized" in skills_data:
                    for cat, s_list in skills_data["categorized"].items():
                        if isinstance(s_list, list):
                            skills_str.extend([str(s).lower() for s in s_list])
            elif isinstance(skills_data, list):
                skills_str = [str(s).lower() for s in skills_data]
            
            edu_list = resume_json.get("education", [])
            if isinstance(edu_list, list):
                edu_str = [str(e.get("degree", "")) + " " + str(e.get("field", "")) + " " + str(e.get("institution", "")) if isinstance(e, dict) else str(e).lower() for e in edu_list]

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
    Canonical domain/family identifiers below stay consistent with the unified rule configuration.
    """



    @classmethod
    def validate_taxonomy_config(cls) -> None:
        """
        Deprecated. Taxonomy is now fully dynamic via PostgreSQL and MSSQL schemas.
        """
        pass


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
            avg_ms = round(cls.classification_time_total_ms / cls.taxonomy_hits, 4) if cls.taxonomy_hits > 0 else 0.0
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

        if dyn_res.match_status in (MatchStatus.DB_MATCH, MatchStatus.PARTIAL_MATCH):
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
            matched_kw = dyn_res.evidence[0].matched_term if dyn_res.evidence else ""
            domain = dyn_res.industry_domain or "Unknown"
            family = dyn_res.industry_department or dyn_res.db_department_name or "Unknown"
            return TaxonomyClassification(
                domain=domain,
                job_family=family,
                compatible_families=(family,),
                matched_rule=f"dynamic:{dyn_res.match_source}",
                matched_branch=0,
                matched_keywords=(matched_kw,) if matched_kw else (),
            )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
        return TaxonomyClassification(
            domain="Unknown",
            job_family="Unknown",
            compatible_families=("Unknown",),
            matched_rule=dyn_res.match_status.value if hasattr(dyn_res.match_status, "value") else str(dyn_res.match_status),
            matched_branch=0,
            matched_keywords=(),
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

        if dyn_res.match_status in (MatchStatus.DB_MATCH, MatchStatus.PARTIAL_MATCH):
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
            domain = dyn_res.industry_domain or "Unknown"
            family = dyn_res.industry_department or dyn_res.db_department_name or "Unknown"
            if domain != "Unknown":
                return TaxonomyClassification(
                    domain=domain,
                    job_family=family,
                    compatible_families=(family,),
                    matched_rule=f"dynamic:{dyn_res.match_source}",
                )

        from app.repositories.department_domain import department_domain_repository
        from app.core.rule_config_manager import RuleConfigManager
        
        tax_rules = RuleConfigManager.get_taxonomy_rules()
        w_exp = tax_rules.evidence_weight_experience
        w_skills = tax_rules.evidence_weight_skills
        w_summary = tax_rules.evidence_weight_summary
        w_edu = tax_rules.evidence_weight_education
        
        combined_text = dto.normalized_full_text.lower()
        exp_text = " ".join(dto.experience_titles).lower()
        skills_text = " ".join(dto.skills).lower()
        summary_text = dto.summary.lower() if dto.summary else ""
        edu_text = " ".join(dto.education).lower()
        
        dept_scores = []
        for matcher in department_domain_repository.get_domain_matchers():
            score = 0.0
            
            # Base text match
            score += matcher.keyword_match_count(combined_text) * 1.0
            
            if exp_text:
                score += matcher.keyword_match_count(exp_text) * w_exp
            if skills_text:
                score += matcher.keyword_match_count(skills_text) * w_skills
            if summary_text:
                score += matcher.keyword_match_count(summary_text) * w_summary
            if edu_text:
                score += matcher.keyword_match_count(edu_text) * w_edu
                
            if score > 0:
                dept_scores.append((score, matcher.domain))

        if dept_scores:
            best_domain = max(dept_scores, key=lambda item: (item[0], -item[1].priority))[1]
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
            return TaxonomyClassification(
                domain=best_domain.domain_name,
                job_family=best_domain.department_name,
                compatible_families=(best_domain.department_name,),
                matched_rule="domain_repository_keyword_fallback",
            )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
        return TaxonomyClassification(
            domain="Unknown",
            job_family="Unknown",
            compatible_families=("Unknown",),
            matched_rule=dyn_res.match_status.value if hasattr(dyn_res.match_status, "value") else str(dyn_res.match_status),
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
            is_compat, status, score = DynamicTaxonomyService.check_family_compatibility(cand_fam, job_family)
            if is_compat and score is not None and score > 0.4:
                return True
        return False

    @classmethod
    def get_metrics(cls) -> dict[str, Any]:
        """Exposes telemetry diagnostics and metrics for TaxonomyClassifier operations."""
        return TaxonomyMetrics.get_metrics()
