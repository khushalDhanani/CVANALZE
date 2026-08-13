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
    responsibilities: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    normalized_full_text: str = ""
    
    # Original-casing strings kept local for case-sensitive acronym matching
    raw_summary: str = ""
    raw_experience_titles: list[str] = Field(default_factory=list)
    raw_responsibilities: list[str] = Field(default_factory=list)
    raw_skills: list[str] = Field(default_factory=list)
    raw_education: list[str] = Field(default_factory=list)

    @classmethod
    def from_resume(cls, cv_text: str, resume_json: dict[str, Any] | None = None) -> "CandidateResumeDTO":
        text_lower = cv_text.lower()
        raw_summary = ""
        raw_exp_titles: list[str] = []
        raw_skills_str: list[str] = []
        raw_edu_str: list[str] = []
        raw_responsibilities: list[str] = []
        
        summary = ""
        exp_titles: list[str] = []
        skills_str: list[str] = []
        edu_str: list[str] = []
        responsibilities: list[str] = []

        if resume_json and isinstance(resume_json, dict):
            raw_summary = str(resume_json.get("summary") or "")
            summary = raw_summary.lower()
            
            exp_list = resume_json.get("work_experience", []) or resume_json.get("experience", [])
            if isinstance(exp_list, list):
                raw_exp_titles = [str(e.get("job_title") or e.get("title") or "") for e in exp_list if isinstance(e, dict)]
                exp_titles = [t.lower() for t in raw_exp_titles]
                for experience in exp_list:
                    if not isinstance(experience, dict):
                        continue
                    for item in experience.get("responsibilities") or []:
                        if isinstance(item, str) and item.strip():
                            raw_responsibilities.append(str(item))
                            responsibilities.append(str(item).lower())
            
            skills_data = resume_json.get("skills")
            if isinstance(skills_data, dict):
                if "all_skills" in skills_data:
                    raw_skills_str = [str(s) for s in skills_data["all_skills"]]
                elif "categorized" in skills_data:
                    for cat, s_list in skills_data["categorized"].items():
                        if isinstance(s_list, list):
                            raw_skills_str.extend([str(s) for s in s_list])
            elif isinstance(skills_data, list):
                raw_skills_str = [str(s) for s in skills_data]
            skills_str = [s.lower() for s in raw_skills_str]
            
            edu_list = resume_json.get("education", [])
            if isinstance(edu_list, list):
                raw_edu_str = [str(e.get("degree", "")) + " " + str(e.get("field", "")) + " " + str(e.get("institution", "")) if isinstance(e, dict) else str(e) for e in edu_list]
                edu_str = [e.lower() for e in raw_edu_str]

        if not summary and not exp_titles and not skills_str:
            raw_summary = cv_text
            summary = text_lower

        combined = f"{text_lower} {summary} {' '.join(exp_titles)} {' '.join(responsibilities)} {' '.join(skills_str)} {' '.join(edu_str)}"
        norm_full_text = re.sub(r"\s+", " ", combined).strip()

        return cls(
            cv_text=cv_text,
            summary=summary,
            experience_titles=exp_titles,
            responsibilities=responsibilities,
            skills=skills_str,
            education=edu_str,
            normalized_full_text=norm_full_text,
            raw_summary=raw_summary,
            raw_experience_titles=raw_exp_titles,
            raw_responsibilities=raw_responsibilities,
            raw_skills=raw_skills_str,
            raw_education=raw_edu_str,
        )


class TaxonomyClassification(BaseModel):
    """Strongly-typed classification result with optional diagnostic telemetry."""

    domain: str
    job_family: str
    compatible_families: tuple[str, ...] = ()
    matched_rule: str | None = None
    matched_branch: int | None = None
    matched_keywords: tuple[str, ...] = ()
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    match_status: MatchStatus = MatchStatus.INSUFFICIENT_EVIDENCE


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
    def classify_vacancy_dto(cls, dto: VacancyDTO, skip_vector: bool = False) -> TaxonomyClassification:
        """Strongly-typed classification of VacancyDTO returning TaxonomyClassification via DynamicTaxonomyService."""
        t0 = time.perf_counter()

        # 1. Try Dynamic Vector & MSSQL taxonomy resolution first
        dyn_res = DynamicTaxonomyService.resolve_vacancy_domain_and_family(
            title=dto.title,
            department=dto.department,
            description=dto.description,
            required_skills=dto.required_skills,
            skip_vector=skip_vector,
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
                confidence=dyn_res.confidence,
                match_status=dyn_res.match_status,
            )

        from app.repositories.department_domain import department_domain_repository
        
        combined_text = f"{dto.title_lower} {dto.department_lower} {dto.normalized_description} {dto.normalized_required_skills}".lower()
        dept_scores = []
        for matcher in department_domain_repository.get_domain_matchers():
            score = matcher.keyword_match_count(combined_text)
            if score > 0:
                dept_scores.append((score, matcher.domain))

        if dept_scores:
            best_domain = max(dept_scores, key=lambda item: (item[0], -item[1].priority))[1]
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
            return TaxonomyClassification(
                domain=best_domain.domain_name,
                job_family=best_domain.department_name or dto.department or "Unknown",
                compatible_families=(best_domain.department_name or dto.department or "Unknown",),
                matched_rule="domain_repository_keyword_fallback",
                matched_branch=0,
                matched_keywords=(),
                confidence=1.0,
                match_status=MatchStatus.DB_MATCH,
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
            confidence=0.0,
            match_status=dyn_res.match_status,
        )

    @classmethod
    def classify_vacancy(cls, job: dict[str, Any] | VacancyDTO | Any, skip_vector: bool = False) -> tuple[str, str]:
        """
        Classifies a job opening into (domain, job_family).
        Accepts VacancyDTO, JobEvaluationContext, or raw dicts.
        Preserves 100% backward compatibility.
        Pass `skip_vector=True` during bulk preprocessing to avoid blocking Ollama calls.
        """
        dto = VacancyDTO.from_job(job)
        classification = cls.classify_vacancy_dto(dto, skip_vector=skip_vector)
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
                    confidence=dyn_res.confidence,
                    match_status=dyn_res.match_status,
                )

        from app.repositories.department_domain import department_domain_repository
        from app.core.rule_config_manager import RuleConfigManager
        
        tax_rules = RuleConfigManager.get_taxonomy_rules()
        w_exp = tax_rules.evidence_weight_experience
        w_skills = tax_rules.evidence_weight_skills
        w_summary = tax_rules.evidence_weight_summary
        w_edu = tax_rules.evidence_weight_education
        
        exp_text = " ".join(dto.raw_experience_titles)
        skills_text = " ".join(dto.raw_skills)
        summary_text = dto.raw_summary if dto.raw_summary else ""
        edu_text = " ".join(dto.raw_education)
        responsibilities_text = " ".join(dto.raw_responsibilities)
        
        dept_scores = []
        for matcher in department_domain_repository.get_domain_matchers():
            score = 0.0
            evidence_sources = 0
            total_matches = 0
            if exp_text:
                matches = matcher.keyword_match_count(exp_text)
                score += matches * w_exp
                evidence_sources += int(matches > 0)
                total_matches += matches
            if skills_text:
                matches = matcher.keyword_match_count(skills_text)
                score += matches * w_skills
                evidence_sources += int(matches > 0)
                total_matches += matches
            if responsibilities_text:
                matches = matcher.keyword_match_count(responsibilities_text)
                score += matches * tax_rules.evidence_weight_responsibilities
                evidence_sources += int(matches > 0)
                total_matches += matches
            if summary_text:
                matches = matcher.keyword_match_count(summary_text)
                score += matches * w_summary
                evidence_sources += int(matches > 0)
                total_matches += matches
            if edu_text and not (exp_text or skills_text or responsibilities_text):
                matches = matcher.keyword_match_count(edu_text)
                score += matches * w_edu
                evidence_sources += int(matches > 0)
                total_matches += matches
                
            if score > 0 and (evidence_sources >= 2 or total_matches >= 2):
                dept_scores.append((score, matcher.domain))

        if dept_scores:
            best_score, best_domain = max(dept_scores, key=lambda item: (item[0], -item[1].priority))
            evidence_weight_total = w_exp + w_skills + tax_rules.evidence_weight_responsibilities + w_summary
            confidence = min(1.0, best_score / evidence_weight_total) if evidence_weight_total > 0 else 0.0
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
            return TaxonomyClassification(
                domain=best_domain.domain_name,
                job_family=best_domain.department_name,
                compatible_families=(best_domain.department_name,),
                matched_rule="domain_repository_keyword_fallback",
                confidence=confidence,
                match_status=MatchStatus.DB_MATCH,
            )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
        return TaxonomyClassification(
            domain="Unknown",
            job_family="Unknown",
            compatible_families=("Unknown",),
            matched_rule=dyn_res.match_status.value if hasattr(dyn_res.match_status, "value") else str(dyn_res.match_status),
            confidence=0.0,
            match_status=dyn_res.match_status,
        )

    @classmethod
    def classify_candidate_with_confidence(
        cls,
        cv_text: str,
        resume_json: dict[str, Any] | None = None,
    ) -> tuple[str, list[str], float, MatchStatus, str | None]:
        """Classify a candidate while preserving the confidence needed by retrieval guards."""
        dto = CandidateResumeDTO.from_resume(cv_text, resume_json=resume_json)
        classification = cls.classify_candidate_dto(dto)
        return (
            classification.domain,
            list(classification.compatible_families),
            classification.confidence,
            classification.match_status,
            classification.matched_rule,
        )

    @classmethod
    def classify_candidate(cls, cv_text: str, resume_json: dict[str, Any] | None = None) -> tuple[str, list[str]]:
        """
        Classifies candidate CV text into primary domain and list of compatible job families.
        Cached once per candidate_full_text string.
        Preserves 100% backward compatibility.
        """
        domain, families, _confidence, _status, _source = cls.classify_candidate_with_confidence(cv_text, resume_json=resume_json)
        return domain, families

    @classmethod
    def are_families_compatible(cls, candidate_families: list[str], job_family: str) -> bool:
        """
        Returns True if candidate_families contains or is compatible with job_family via DynamicTaxonomyService or legacy config map.
        Preserves 100% backward compatibility.
        """
        from app.core.rule_config_manager import RuleConfigManager

        compatibility_threshold = RuleConfigManager.get_taxonomy_rules().family_compatibility_min_score
        
        # 1. Exact string match
        for cand_fam in candidate_families:
            if cand_fam.strip().lower() == job_family.strip().lower():
                return True

        # 2. Canonical DB ID / Hierarchy Check
        from app.core.database import PostgresAppSession
        if PostgresAppSession is not None:
            try:
                with PostgresAppSession() as session:
                    from app.models.taxonomy import JobFamilyMaster, DomainMaster
                    job_domain_ids = set()
                    
                    # Resolve Job Family
                    jf = session.query(JobFamilyMaster).filter(JobFamilyMaster.family_name.ilike(job_family)).first()
                    if jf:
                        job_domain_ids.add(jf.domain_id)
                    else:
                        jd = session.query(DomainMaster).filter(DomainMaster.domain_name.ilike(job_family)).first()
                        if jd:
                            job_domain_ids.add(jd.domain_id)
                            
                    # Resolve Candidate Families
                    for cand_fam in candidate_families:
                        cf = session.query(JobFamilyMaster).filter(JobFamilyMaster.family_name.ilike(cand_fam)).first()
                        if cf and cf.domain_id in job_domain_ids:
                            return True
                        if not cf:
                            cd = session.query(DomainMaster).filter(DomainMaster.domain_name.ilike(cand_fam)).first()
                            if cd and cd.domain_id in job_domain_ids:
                                return True
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Taxonomy ID Canonicalization failed: {e}")

        # 3. Explicit cross-family compatibility mapping fallback
        for cand_fam in candidate_families:
            is_compat, status, score = DynamicTaxonomyService.check_family_compatibility(cand_fam, job_family)
            if is_compat and score is not None and score > compatibility_threshold:
                return True
                
        return False

    @classmethod
    def get_metrics(cls) -> dict[str, Any]:
        """Exposes telemetry diagnostics and metrics for TaxonomyClassifier operations."""
        return TaxonomyMetrics.get_metrics()
