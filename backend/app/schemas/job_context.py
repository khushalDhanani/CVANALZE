# backend/app/schemas/job_context.py
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.rule_config_manager import RuleConfigManager
from app.services.candidate_domain_service import CandidateDomainService
from app.services.job_taxonomy import TaxonomyClassifier


@dataclass
class JobEvaluationContext:
    """
    Encapsulates pre-computed vacancy state for CV scoring.

    Pre-classifies vacancy taxonomy (domain and job family), pre-extracts
    department terms, title words, software requirement flags, and non-IT job
    flags ONCE when vacancies are loaded, preventing redundant per-candidate
    computation across multi-vacancy matching loops.
    """

    job_id: str
    title: str
    title_lower: str
    title_words: set[str]
    department: str
    department_lower: str
    dept_terms: list[str]
    required_skills: list[str]
    preferred_keywords: list[str]
    min_experience_years: float | None
    max_experience_years: float | None
    max_ctc: float | None
    education_requirements: str | None
    certifications: str | None
    technologies: list[str]
    responsibilities: list[str]
    vac_tax_domain: str
    vac_family: str
    is_non_it_job: bool
    has_software_req: bool
    dept_term_patterns: list[re.Pattern[str]] = field(default_factory=list)
    raw_job: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, job: dict[str, Any]) -> "JobEvaluationContext":
        job_id = str(job.get("id") or job.get("vacancy_id") or "")
        title = str(job.get("title") or "")
        title_lower = title.strip().lower()

        raw_words = set(re.findall(r"\w+", title_lower))
        config_noise = RuleConfigManager.get_term_matching_assets().get("noise_words", set())
        default_noise = {"senior", "junior", "lead", "head", "manager", "developer", "engineer", "specialist"}
        noise = config_noise.union(default_noise)
        title_words = raw_words - noise

        department = str(job.get("department_name") or job.get("department") or "")
        department_lower = department.strip().lower()
        dept_terms = CandidateDomainService.extract_department_domain_terms(department)
        dept_term_patterns = [
            re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE)
            for t in dept_terms
        ]

        required_skills = list(job.get("required_skills") or [])
        preferred_keywords = list(job.get("preferred_keywords") or [])
        min_experience_years = job.get("min_experience_years")
        max_experience_years = job.get("max_experience_years")
        max_ctc = job.get("max_ctc")
        education_requirements = job.get("education_requirements") or job.get("required_education")
        certifications = job.get("certifications") or job.get("required_certifications")
        technologies = list(job.get("technologies") or [])
        responsibilities = list(job.get("responsibilities") or [])

        # 1. Pre-classify Vacancy Taxonomy
        pre_domain = job.get("_precomputed_domain") or job.get("domain")
        pre_family = job.get("_precomputed_job_family") or job.get("job_family")
        if pre_domain and pre_family:
            vac_tax_domain, vac_family = str(pre_domain), str(pre_family)
        else:
            vac_tax_domain, vac_family = TaxonomyClassifier.classify_vacancy(job)

        # 2. Pre-compute Guard Flags
        compiled_guard = RuleConfigManager.get_compiled_cross_domain_guard()
        is_non_it_job = any(
            p.search(title) or p.search(department)
            for p in compiled_guard["non_it_job_patterns"]
        )
        has_software_req = any(
            any(p.search(str(s)) for p in compiled_guard["software_requirement_patterns"])
            for s in required_skills
        )

        return cls(
            job_id=job_id,
            title=title,
            title_lower=title_lower,
            title_words=title_words,
            department=department,
            department_lower=department_lower,
            dept_terms=dept_terms,
            dept_term_patterns=dept_term_patterns,
            required_skills=required_skills,
            preferred_keywords=preferred_keywords,
            min_experience_years=min_experience_years,
            max_experience_years=max_experience_years,
            max_ctc=max_ctc,
            education_requirements=str(education_requirements) if education_requirements else None,
            certifications=str(certifications) if certifications else None,
            technologies=technologies,
            responsibilities=responsibilities,
            vac_tax_domain=vac_tax_domain,
            vac_family=vac_family,
            is_non_it_job=is_non_it_job,
            has_software_req=has_software_req,
            raw_job=job,
        )

    @classmethod
    def from_jobs(cls, jobs: list[dict[str, Any]]) -> list["JobEvaluationContext"]:
        """Pre-processes a list of raw job dicts into JobEvaluationContexts."""
        return [cls.create(j) for j in jobs]
