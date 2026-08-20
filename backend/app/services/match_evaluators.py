from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.rule_config_manager import RuleConfigManager
from app.schemas.analysis import OptimizedVacancyMatch
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.job_context import JobEvaluationContext
from app.schemas.match import (
    DualEvidence,
    MandatoryFailureDetails,
    RequirementEvaluation,
    RequirementStatus,
    RequirementTier,
)
from app.schemas.scoring_config import ScoringConfig
from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
from app.services.job_taxonomy import TaxonomyClassifier

_EXPERIENCE_CLAUSE_RE = re.compile(
    r"\b\d+\s*\+?\s*(?:to\s*\d+\s*)?years?\b", re.IGNORECASE
)

def _stop_phrases() -> frozenset[str]:
    return RuleConfigManager.get_term_matching_assets().get("stop_phrases", frozenset())


def is_ignorable_requirement(term: str | None) -> bool:
    """True when a parsed JD requirement is a JD-parsing artifact rather than a
    real, matchable skill: empty strings, stop words, prose/sentence fragments,
    and generic years-of-experience clauses.

    Such artifacts must be skipped (never FAIL, never fabricate a match) so they
    neither penalize candidates nor inflate confidence.
    """
    if not term or not term.strip():
        return True
    term_clean = term.strip()
    term_lower = term_clean.lower()
    if term_lower in _stop_phrases():
        return True
    if _EXPERIENCE_CLAUSE_RE.search(term_lower):
        return True
    # Prose with an embedded sentence break is a JD parsing fragment.
    if re.search(r"[.!?]\s+\S", term_clean):
        return True
    # Sentences (>= 6 words) are not skills.
    return len(re.findall(r"[a-z0-9]+", term_lower)) >= 6


def _share_root_family(candidate_family: str | None, vacancy_family: str | None) -> bool:
    if not candidate_family or not vacancy_family:
        return False
    parenthetical = re.compile(r"\s*\([^)]*\)", re.IGNORECASE)
    candidate_root = parenthetical.sub("", candidate_family).split("-")[0].strip().lower()
    vacancy_root = parenthetical.sub("", vacancy_family).split("-")[0].strip().lower()
    if not candidate_root or not vacancy_root:
        return False
    return candidate_root == vacancy_root or candidate_root in vacancy_root or vacancy_root in candidate_root


def _education_requirement_matches(
    context: CandidateAnalysisContext,
    education_requirement: str,
    extract_term_matches_fn: Callable[[str, list[str]], tuple[list[str], list[str]]] | None = None,
) -> bool:
    from app.services.education_resolver import EducationRequirementResolver, EducationMatchStatus

    cand_edu: list[Any] = list(context.education_evidence)
    if isinstance(context.resume_json, dict):
        cand_edu.extend(context.resume_json.get("education", []) or [])
    if context.optimized_profile:
        cand_edu.extend(context.optimized_profile.education_domains)

    outcome = EducationRequirementResolver.evaluate_education_requirement(cand_edu, education_requirement)
    return outcome.status in (EducationMatchStatus.EXACT, EducationMatchStatus.EQUIVALENT)


def _has_relevant_experience(
    context: CandidateAnalysisContext,
    job: JobEvaluationContext,
    matched_responsibilities: list[str] | None = None,
    matched_skills: list[str] | None = None,
) -> bool:
    """Return whether verified experience is relevant to the vacancy evidence."""
    if context.candidate_experience is None or context.candidate_experience <= 0:
        return False

    if matched_skills:
        return True

    if job.vac_family not in (None, "Unknown"):
        if TaxonomyClassifier.are_families_compatible(context.cand_families, job.vac_family):
            return True
        if any(_share_root_family(candidate_family, job.vac_family) for candidate_family in context.cand_families):
            return True

    if context.cand_tax_domain not in (None, "", "Unknown") and job.vac_tax_domain not in (None, "", "Unknown"):
        if context.cand_tax_domain == job.vac_tax_domain:
            return True

    if matched_responsibilities:
        return True

    if context.current_role and job.title_words:
        current_role_words = set(re.findall(r"\w+", context.current_role.lower()))
        if current_role_words.intersection(job.title_words):
            return True

    if not context.current_role and (not job.vac_family or job.vac_family == "Unknown"):
        return True

    return False


def _calculate_relevant_experience(
    context: CandidateAnalysisContext,
    job: JobEvaluationContext,
    extract_term_matches_fn: Any
) -> float | None:
    if not context.normalized_resume or not context.normalized_resume.employment:
        return 0.0

    from datetime import datetime

    from app.core.rule_config_manager import RuleConfigManager
    from app.services.experience_calculator import ExperienceCalculator
    config = RuleConfigManager.get_config()
    noise_words = set(w.lower() for w in config.scoring.match.term_matching.noise_words)
    if not noise_words:
        noise_words = {"manager", "senior", "lead", "associate", "analyst", "specialist", "executive", "director", "engineer", "developer", "consultant"}
    sp = config.scoring.match.scoring_parameters
    threshold_relevant = sp.experience_relevance_threshold # e.g. 7.0
    threshold_partial = sp.experience_partial_threshold # e.g. 5.5

    valid_intervals = []
    has_unparsed = False
    
    from app.services.job_taxonomy import DynamicTaxonomyService
    
    # Pre-calculate job taxonomy family for contradiction check
    job_family = job.vac_family if job.vac_family not in (None, "Unknown") else None
    job_domain = job.vac_tax_domain if job.vac_tax_domain not in (None, "Unknown") else None

    for emp in context.normalized_resume.employment:
        evidence_score = 0.0
        
        emp_title = emp.job_title.normalized_value or emp.job_title.raw_value or ""
        emp_text = " ".join([emp_title, *emp.responsibilities, *emp.evidence]).lower()
        
        # 1. Block-Level Taxonomy Alignment (+5.0)
        # We classify this specific employment block independently
        block_tax = DynamicTaxonomyService.resolve_vacancy_domain_and_family(
            title=emp_title,
            department="",
            description=" ".join(emp.responsibilities),
            required_skills=emp.evidence,
            skip_vector=False
        )
        
        # TaxonomyClassification returns 'job_family' and 'domain' (or 'industry_department' if DynamicTaxonomyResolution)
        block_family = getattr(block_tax, "job_family", getattr(block_tax, "industry_department", None))
        block_domain = getattr(block_tax, "domain", getattr(block_tax, "industry_domain", None))
        
        is_same_canonical_domain = False
        if block_domain and block_domain != "Unknown" and job_domain and job_domain != "Unknown":
            if block_domain.strip().lower() == job_domain.strip().lower():
                is_same_canonical_domain = True

        from app.services.job_taxonomy import TaxonomyClassifier
        
        if job_family and block_family:
            is_parent_child = False
            if is_same_canonical_domain and (job_family.strip().lower() == job_domain.strip().lower() or block_family.strip().lower() == block_domain.strip().lower()):
                is_parent_child = True

            if TaxonomyClassifier.are_families_compatible([block_family], job_family):
                evidence_score += sp.block_weight_taxonomy
            elif is_same_canonical_domain and is_parent_child:
                evidence_score += sp.block_weight_taxonomy
            elif is_same_canonical_domain:
                evidence_score += (sp.block_weight_taxonomy * 0.5)
            else:
                # Contradiction: Block domain explicitly misaligns and no evidence bridging
                evidence_score -= sp.block_weight_taxonomy

        # 2. Job Title Match (Filtered) (+3.0)
        if emp_title and job.title_words:
            title_words = set(re.findall(r"\w+", emp_title.lower()))
            filtered_title_words = title_words - noise_words
            filtered_job_words = job.title_words - noise_words
            
            if filtered_title_words.intersection(filtered_job_words):
                evidence_score += sp.block_weight_title
        
        # 3. Responsibilities / Skills Density (+2.0 per match)
        matched_skills = 0
        if job.required_skills:
            matched, _ = extract_term_matches_fn(emp_text, job.required_skills)
            matched_skills += len(matched)
            
        if job.responsibilities:
            matched, _ = extract_term_matches_fn(emp_text, job.responsibilities)
            matched_skills += len(matched)
            
        evidence_score += (matched_skills * sp.block_weight_skills)

        # Threshold Evaluation
        if evidence_score >= threshold_relevant:
            status = "RELEVANT"
        elif evidence_score >= threshold_partial:
            status = "PARTIAL"
        else:
            status = "NOT_RELEVANT"

        if status == "RELEVANT":
            if not emp.interval.start_date:
                has_unparsed = True
                continue
            
            start_date = datetime.fromisoformat(emp.interval.start_date)
            end_date = datetime.fromisoformat(emp.interval.end_date) if emp.interval.end_date else (datetime.now() if emp.interval.is_current else start_date)
            valid_intervals.append((start_date, end_date))

    if has_unparsed and not valid_intervals:
        return None

    if not valid_intervals:
        return 0.0

    merged = ExperienceCalculator._merge_intervals(valid_intervals)
    total_days = sum((end - start).days + 1 for start, end in merged)
    return round(total_days / 365.25, 1)


@dataclass
class RequirementEvaluationResults:
    mandatory_reqs: list[RequirementEvaluation] = field(default_factory=list)
    preferred_reqs: list[RequirementEvaluation] = field(default_factory=list)
    optional_reqs: list[RequirementEvaluation] = field(default_factory=list)
    mandatory_failures: list[MandatoryFailureDetails] = field(default_factory=list)
    matched_criteria: list[str] = field(default_factory=list)
    missing_criteria: list[str] = field(default_factory=list)
    evidence_map: dict[str, DualEvidence] = field(default_factory=dict)
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    inferred_skills: list[str] = field(default_factory=list)
    unverified_skills: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)


@dataclass
class ComponentScoreResults:
    role_score: float
    skills_score: float | None
    experience_score: float | None
    education_score: float | None
    domain_score: float | None
    technology_score: float | None
    certification_score: float | None
    responsibilities_score: float | None
    component_coverage: float
    raw_score: float
    final_score: float
    hr_review_required: bool
    reason_str: str

    @property
    def coverage(self) -> float:
        """Backwards compatibility alias for component_coverage."""
        return self.component_coverage


@dataclass
class CrossDomainGuardResults:
    final_score: float
    domain_score: float | None
    reason_str: str
    is_domain_capped: bool
    domain_capped_reason: str | None
    vac_tax_domain: str
    vac_family: str
    additional_mandatory_failures: list[MandatoryFailureDetails] = field(default_factory=list)


@dataclass
class RecommendationResults:
    classification: str
    recommendation: str
    confidence_val: float
    reason_str: str


class RequirementEvaluator:
    """Evaluates mandatory skills, experience, education, certification, CTC budget, preferred keywords, and max experience."""

    @staticmethod
    def _create_evidence(
        cv_ev: str,
        vac_ev: str,
        confidence_score: float = 1.0,
        provenance: str = "VERIFIED_CV",
        source_section: str | None = None,
    ) -> DualEvidence:
        return DualEvidence(
            cv_evidence=cv_ev,
            vacancy_evidence=vac_ev,
            confidence_score=confidence_score,
            provenance=provenance,
            source_section=source_section,
        )

    @staticmethod
    def _create_requirement(
        req_id: str,
        desc: str,
        tier: RequirementTier,
        status: RequirementStatus,
        evidence: DualEvidence,
        failure_reason: str | None = None,
    ) -> RequirementEvaluation:
        return RequirementEvaluation(
            requirement_id=req_id,
            description=desc,
            tier=tier,
            status=status,
            evidence=evidence,
            failure_reason=failure_reason,
        )

    @staticmethod
    def _create_failure(
        failure_code: str,
        req_id: str,
        desc: str,
        reason: str,
        penalty: float,
    ) -> MandatoryFailureDetails:
        return MandatoryFailureDetails(
            failure_code=failure_code,
            requirement_id=req_id,
            description=desc,
            reason=reason,
            score_impact=penalty,
        )

    @classmethod
    def evaluate(
        cls,
        context: CandidateAnalysisContext,
        job: JobEvaluationContext | dict[str, Any],
        llm_match: OptimizedVacancyMatch | None = None,
        scoring_config: ScoringConfig | dict[str, Any] | None = None,
        extract_term_matches_fn: Callable[[str, list[str]], tuple[list[str], list[str]]] | None = None,
        penalty_per_item: float | None = None,
        mode: str = "FULL",
        **kwargs: Any,
    ) -> RequirementEvaluationResults:
        job_ctx = job if isinstance(job, JobEvaluationContext) else JobEvaluationContext.create(job)
        if extract_term_matches_fn is None:
            from app.services.scoring_engine import ScoringEngine

            extract_term_matches_fn = ScoringEngine._extract_term_matches

        typed_config = scoring_config if isinstance(scoring_config, ScoringConfig) else ScoringConfig.load(scoring_config if isinstance(scoring_config, dict) else None)
        penalty = penalty_per_item if penalty_per_item is not None else typed_config.penalty_per_item

        results = RequirementEvaluationResults()

        req_skills = job_ctx.required_skills
        skills_are_mandatory = job_ctx.required_skills_are_mandatory
        pref_keywords = job_ctx.preferred_keywords
        min_exp = job_ctx.min_experience_years
        max_exp = job_ctx.max_experience_years
        max_ctc = job_ctx.max_ctc
        education_req = job_ctx.education_requirements
        certification_req = job_ctx.certifications

        # 1. Mandatory Skills
        matched_skills, missing_skills = extract_term_matches_fn(context.norm_text, req_skills)
        
        # Determine LLM provenance
        llm_core_matched, _ = extract_term_matches_fn(" ".join(context.llm_core_skills), req_skills)
        llm_inferred_matched, _ = extract_term_matches_fn(" ".join(context.llm_inferred_skills), req_skills)

        results.matched_skills = matched_skills
        results.missing_skills = missing_skills

        matched_responsibilities, _ = extract_term_matches_fn(context.domain_candidate_text or context.norm_text, job_ctx.responsibilities)
        has_relevant_experience = _has_relevant_experience(context, job_ctx, matched_responsibilities, matched_skills)

        for skill in req_skills:
            if is_ignorable_requirement(skill):
                continue
            req_id = f"req_skill_{skill.lower().replace(' ', '_')}"
            requirement_label = "Mandatory Skill Requirement" if skills_are_mandatory else "Additional Knowledge Requirement"
            vac_ev = f"{requirement_label}: {skill}"
            if skill in matched_skills:
                provenance = "VERIFIED_CV"
                cv_ev = f"[{provenance}] CV explicitly contains skill: '{skill}'"
                if skill in llm_core_matched:
                    provenance = "GROUNDED_LLM"
                    cv_ev = f"[{provenance}] LLM core skill grounded in explicit CV text: '{skill}'"
                
                ev = cls._create_evidence(cv_ev, vac_ev, confidence_score=1.0, provenance=provenance, source_section="skills")
                target_requirements = results.mandatory_reqs if skills_are_mandatory else results.preferred_reqs
                target_requirements.append(
                    cls._create_requirement(
                        req_id,
                        f"Skill: {skill}",
                        RequirementTier.MANDATORY if skills_are_mandatory else RequirementTier.PREFERRED,
                        RequirementStatus.SATISFIED,
                        ev,
                    )
                )
                results.evidence_map[req_id] = ev
                results.matched_criteria.append(f"Skill ({skill})")
            elif skill in llm_inferred_matched or skill in llm_core_matched:
                provenance = "INFERRED_LLM" if skill in llm_inferred_matched else "UNVERIFIED_LLM"
                if skills_are_mandatory:
                    cv_ev = f"[{provenance}] LLM generated skill '{skill}', but cannot satisfy mandatory requirement."
                    ev = cls._create_evidence(cv_ev, vac_ev, confidence_score=0.0, provenance=provenance, source_section="skills")
                    reason = f"Candidate CV lacks explicit/grounded evidence for mandatory skill '{skill}'."
                    results.mandatory_reqs.append(
                        cls._create_requirement(
                            req_id,
                            f"Skill: {skill}",
                            RequirementTier.MANDATORY,
                            RequirementStatus.FAILED,
                            ev,
                            failure_reason=reason,
                        )
                    )
                    results.evidence_map[req_id] = ev
                    results.mandatory_failures.append(cls._create_failure("MISSING_MANDATORY_SKILL", req_id, f"Mandatory Skill: {skill}", reason, penalty))
                    results.missing_criteria.append(f"Mandatory Skill ({skill})")
                else:
                    cv_ev = f"[{provenance}] LLM generated skill: '{skill}'"
                    ev = cls._create_evidence(cv_ev, vac_ev, confidence_score=0.7, provenance=provenance, source_section="llm_inferred")
                    results.preferred_reqs.append(
                        cls._create_requirement(
                            req_id,
                            f"Skill: {skill}",
                            RequirementTier.PREFERRED,
                            RequirementStatus.SATISFIED,
                            ev,
                        )
                    )
                    results.evidence_map[req_id] = ev
                    results.matched_criteria.append(f"Skill ({skill})")
                    # Move from missing to inferred/unverified
                    if skill in results.missing_skills:
                        results.missing_skills.remove(skill)
                        if provenance == "INFERRED_LLM":
                            results.inferred_skills.append(skill)
                        else:
                            results.unverified_skills.append(skill)
            else:
                cv_ev = f"[MISSING] CV missing required skill: '{skill}'"
                ev = cls._create_evidence(cv_ev, vac_ev, confidence_score=0.0, provenance="NO_EVIDENCE", source_section=None)
                reason = f"Candidate CV lacks documented skill '{skill}'."
                target_requirements = results.mandatory_reqs if skills_are_mandatory else results.preferred_reqs
                target_requirements.append(
                    cls._create_requirement(
                        req_id,
                        f"Skill: {skill}",
                        RequirementTier.MANDATORY if skills_are_mandatory else RequirementTier.PREFERRED,
                        RequirementStatus.FAILED,
                        ev,
                        failure_reason=reason,
                    )
                )
                results.evidence_map[req_id] = ev
                if skills_are_mandatory:
                    results.mandatory_failures.append(cls._create_failure("MISSING_MANDATORY_SKILL", req_id, f"Mandatory Skill: {skill}", reason, penalty))
                    results.missing_criteria.append(f"Mandatory Skill ({skill})")
                else:
                    results.missing_criteria.append(f"Skill Gap ({skill})")

        # 2. Preferred Keywords
        matched_keywords, missing_keywords = extract_term_matches_fn(context.norm_text, pref_keywords)
        results.matched_keywords = matched_keywords
        results.missing_keywords = missing_keywords

        for kw in pref_keywords:
            req_id = f"req_pref_{kw.lower().replace(' ', '_')}"
            vac_ev = f"Preferred Keyword Requirement: {kw}"
            if kw in matched_keywords:
                cv_ev = f"CV contains preferred keyword: '{kw}'"
                ev = cls._create_evidence(cv_ev, vac_ev, confidence_score=1.0, provenance="VERIFIED_CV", source_section="skills")
                results.preferred_reqs.append(
                    cls._create_requirement(
                        req_id,
                        f"Preferred Keyword: {kw}",
                        RequirementTier.PREFERRED,
                        RequirementStatus.SATISFIED,
                        ev,
                    )
                )
                results.evidence_map[req_id] = ev
                results.matched_criteria.append(f"Preferred Keyword ({kw})")

        # 3. Mandatory Minimum Experience
        if min_exp is not None:
            req_id = "req_min_experience"
            vac_ev = f"Mandatory Minimum Experience: {min_exp} years"
            if context.candidate_experience is not None and context.candidate_experience >= min_exp:
                cv_ev = f"Candidate experience {context.candidate_experience} years meets minimum requirement ({min_exp} years)"
                ev = cls._create_evidence(cv_ev, vac_ev, confidence_score=1.0, provenance="VERIFIED_TIMELINE", source_section="employment")
                results.mandatory_reqs.append(
                    cls._create_requirement(
                        req_id,
                        f"Min Experience: {min_exp} years",
                        RequirementTier.MANDATORY,
                        RequirementStatus.SATISFIED,
                        ev,
                    )
                )
                results.evidence_map[req_id] = ev
                results.matched_criteria.append(f"Min Experience ({min_exp} years)")
            elif context.candidate_experience is None:
                cv_ev = f"Candidate experience is unquantifiable or missing from CV (NOT_ASSESSABLE, required: {min_exp} years)"
                reason = f"Candidate experience details are unavailable/unquantifiable for required minimum ({min_exp} yrs)."
                ev = cls._create_evidence(cv_ev, vac_ev, confidence_score=0.0, provenance="NO_EVIDENCE", source_section="employment")
                results.mandatory_reqs.append(
                    cls._create_requirement(
                        req_id,
                        f"Min Experience: {min_exp} years",
                        RequirementTier.MANDATORY,
                        RequirementStatus.NOT_ASSESSABLE,
                        ev,
                        failure_reason=reason,
                    )
                )
                results.evidence_map[req_id] = ev
                results.mandatory_failures.append(cls._create_failure("EXPERIENCE_UNKNOWN", req_id, f"Min Experience: {min_exp} years", reason, penalty))
                results.missing_criteria.append(f"Min Experience ({min_exp} years)")
            else:
                exp_val = context.candidate_experience
                cv_ev = f"Candidate experience {exp_val} years is below minimum required ({min_exp} years)"
                reason = f"Candidate experience ({exp_val} yrs) is less than required minimum ({min_exp} yrs)."
                ev = cls._create_evidence(cv_ev, vac_ev, confidence_score=0.0, provenance="VERIFIED_TIMELINE", source_section="employment")
                results.mandatory_reqs.append(
                    cls._create_requirement(
                        req_id,
                        f"Min Experience: {min_exp} years",
                        RequirementTier.MANDATORY,
                        RequirementStatus.FAILED,
                        ev,
                        failure_reason=reason,
                    )
                )
                results.evidence_map[req_id] = ev
                results.mandatory_failures.append(cls._create_failure("MIN_EXPERIENCE_FAILED", req_id, f"Min Experience: {min_exp} years", reason, penalty))
                results.missing_criteria.append(f"Min Experience ({min_exp} years)")

        # 4. Education Requirement Evaluation
        if education_req:
            req_id = "req_education"
            vac_ev = f"Education Requirement: {education_req}"
            from app.services.education_resolver import EducationRequirementResolver, EducationMatchStatus

            cand_edu: list[Any] = list(context.education_evidence)
            if isinstance(context.resume_json, dict):
                cand_edu.extend(context.resume_json.get("education", []) or [])
            if context.optimized_profile:
                cand_edu.extend(context.optimized_profile.education_domains)

            edu_outcome = EducationRequirementResolver.evaluate_education_requirement(cand_edu, str(education_req))
            is_mandatory_edu = getattr(job_ctx, "education_is_mandatory", False)
            tier = RequirementTier.MANDATORY if is_mandatory_edu else RequirementTier.PREFERRED

            if edu_outcome.status in (EducationMatchStatus.EXACT, EducationMatchStatus.EQUIVALENT):
                cv_ev = f"[{edu_outcome.status}] {edu_outcome.reason}"
                ev = cls._create_evidence(cv_ev, vac_ev, confidence_score=edu_outcome.confidence, provenance="VERIFIED_CV", source_section="education")
                target_reqs = results.mandatory_reqs if is_mandatory_edu else results.preferred_reqs
                target_reqs.append(
                    cls._create_requirement(
                        req_id,
                        f"Education: {education_req}",
                        tier,
                        RequirementStatus.SATISFIED,
                        ev,
                    )
                )
                results.evidence_map[req_id] = ev
                results.matched_criteria.append(f"Education ({education_req})")
            else:
                cv_ev = f"[{edu_outcome.status}] {edu_outcome.reason}"
                ev = cls._create_evidence(cv_ev, vac_ev, confidence_score=0.0, provenance="NO_EVIDENCE", source_section="education")
                reason = edu_outcome.reason
                target_reqs = results.mandatory_reqs if is_mandatory_edu else results.preferred_reqs
                target_reqs.append(
                    cls._create_requirement(
                        req_id,
                        f"Education: {education_req}",
                        tier,
                        RequirementStatus.FAILED,
                        ev,
                        failure_reason=reason,
                    )
                )
                results.evidence_map[req_id] = ev
                fail_code = edu_outcome.failure_code or "MISSING_EDUCATION"
                if is_mandatory_edu:
                    results.mandatory_failures.append(
                        cls._create_failure(
                            fail_code,
                            req_id,
                            f"Mandatory Education: {education_req}",
                            reason,
                            penalty,
                        )
                    )
                    results.missing_criteria.append(f"Mandatory Education ({education_req})")
                else:
                    results.missing_criteria.append(f"Education Mismatch ({education_req})")

        # 5. Mandatory Certification Requirement Evaluation
        if certification_req:
            req_id = "req_certification"
            vac_ev = f"Mandatory Certification Requirement: {certification_req}"
            from app.services.certification_resolver import CertificationResolver, CertificationMatchStatus

            cand_certs: list[str] = list(context.education_evidence)
            if context.optimized_profile and context.optimized_profile.certifications:
                cand_certs.extend(context.optimized_profile.certifications)
            if isinstance(context.resume_json, dict):
                cand_certs.extend(context.resume_json.get("certifications", []) or [])

            cert_outcome = CertificationResolver.match_certification(cand_certs, str(certification_req))
            if cert_outcome.status in (CertificationMatchStatus.EXACT, CertificationMatchStatus.EQUIVALENT):
                cv_ev = f"[{cert_outcome.status}] {cert_outcome.reason}"
                ev = cls._create_evidence(cv_ev, vac_ev, confidence_score=cert_outcome.confidence, provenance="VERIFIED_CV", source_section="certifications")
                results.mandatory_reqs.append(
                    cls._create_requirement(
                        req_id,
                        f"Certification: {certification_req}",
                        RequirementTier.MANDATORY,
                        RequirementStatus.SATISFIED,
                        ev,
                    )
                )
                results.evidence_map[req_id] = ev
                results.matched_criteria.append(f"Certification ({certification_req})")
            else:
                cv_ev = f"[NOT_MATCHED] {cert_outcome.reason}"
                ev = cls._create_evidence(cv_ev, vac_ev, confidence_score=0.0, provenance="NO_EVIDENCE", source_section="certifications")
                reason = cert_outcome.reason
                results.mandatory_reqs.append(
                    cls._create_requirement(
                        req_id,
                        f"Certification: {certification_req}",
                        RequirementTier.MANDATORY,
                        RequirementStatus.FAILED,
                        ev,
                        failure_reason=reason,
                    )
                )
                results.evidence_map[req_id] = ev
                results.mandatory_failures.append(
                    cls._create_failure(
                        "MISSING_CERTIFICATION",
                        req_id,
                        f"Mandatory Certification: {certification_req}",
                        reason,
                        penalty,
                    )
                )
                results.missing_criteria.append(f"Mandatory Certification ({certification_req})")

        # 6. Mandatory CTC Budget
        if context.candidate_ctc is not None and max_ctc is not None and context.candidate_ctc > max_ctc:
            req_id = "req_max_ctc"
            vac_ev = f"Mandatory Maximum Budget CTC: {max_ctc}"
            cv_ev = f"Candidate CTC {context.candidate_ctc} exceeds maximum budget ({max_ctc})"
            ev = cls._create_evidence(cv_ev, vac_ev, confidence_score=0.0, provenance="CANDIDATE_CTC", source_section="salary")
            reason = f"Candidate CTC requirement ({context.candidate_ctc}) exceeds maximum budget ({max_ctc})."
            results.mandatory_reqs.append(
                cls._create_requirement(
                    req_id,
                    f"Max CTC: {max_ctc}",
                    RequirementTier.MANDATORY,
                    RequirementStatus.FAILED,
                    ev,
                    failure_reason=reason,
                )
            )
            results.evidence_map[req_id] = ev
            results.mandatory_failures.append(cls._create_failure("CTC_MISMATCH", req_id, f"Max CTC Budget: {max_ctc}", reason, penalty))
            results.missing_criteria.append(f"Max CTC Budget ({max_ctc})")

        # 7. Preferred Upper Experience Limit
        if max_exp is not None and context.candidate_experience is not None and has_relevant_experience:
            req_id = "req_max_experience"
            vac_ev = f"Preferred Upper Experience Limit: {max_exp} years"
            if context.candidate_experience <= max_exp:
                cv_ev = f"Candidate experience {context.candidate_experience} years is within preferred upper bound ({max_exp} years)"
                ev = cls._create_evidence(cv_ev, vac_ev, confidence_score=1.0, provenance="VERIFIED_TIMELINE", source_section="employment")
                results.preferred_reqs.append(
                    cls._create_requirement(
                        req_id,
                        f"Max Experience: {max_exp} years",
                        RequirementTier.PREFERRED,
                        RequirementStatus.SATISFIED,
                        ev,
                    )
                )
                results.evidence_map[req_id] = ev
                results.matched_criteria.append(f"Max Experience ({max_exp} years)")
            else:
                cv_ev = f"Candidate experience {context.candidate_experience} years exceeds preferred upper bound ({max_exp} years)"
                ev = cls._create_evidence(cv_ev, vac_ev, confidence_score=0.5, provenance="VERIFIED_TIMELINE", source_section="employment")
                results.preferred_reqs.append(
                    cls._create_requirement(
                        req_id,
                        f"Max Experience: {max_exp} years",
                        RequirementTier.PREFERRED,
                        RequirementStatus.PARTIALLY_SATISFIED,
                        ev,
                        failure_reason=f"Candidate experience exceeds preferred upper limit ({max_exp} years).",
                    )
                )
                results.evidence_map[req_id] = ev

        return results


class CareerTransitionEvaluator:
    """Evaluates dynamic career transition detection between current role and target job title."""

    @classmethod
    def evaluate(
        cls,
        context: CandidateAnalysisContext,
        job: JobEvaluationContext | dict[str, Any],
        llm_match: OptimizedVacancyMatch | None = None,
        **kwargs: Any,
    ) -> tuple[bool, str | None, set[str]]:
        job_ctx = job if isinstance(job, JobEvaluationContext) else JobEvaluationContext.create(job)
        job_title = job_ctx.title
        career_transition_detected = False
        career_transition_note = None
        common_words: set[str] = set()

        if context.current_role and job_title:
            current_clean = context.current_role.strip().lower()
            current_words = set(re.findall(r"\w+", current_clean))
            common_words = current_words.intersection(job_ctx.title_words)
            if not common_words and current_clean != job_ctx.title_lower:
                career_transition_detected = True
                career_transition_note = f"Dynamic career transition detected: Current role '{context.current_role}' to Target role '{job_title}'."
                if llm_match and llm_match.career_transition_note:
                    career_transition_note += f" LLM analysis: {llm_match.career_transition_note}"

        return career_transition_detected, career_transition_note, common_words


class ComponentScoreEvaluator:
    """Computes multi-dimensional component scores and weighted sum raw score."""

    @classmethod
    def evaluate(
        cls,
        context: CandidateAnalysisContext,
        job: JobEvaluationContext | dict[str, Any],
        req_results: RequirementEvaluationResults,
        transition_detected: bool,
        common_words: set[str],
        llm_match: OptimizedVacancyMatch | None = None,
        scoring_config: ScoringConfig | dict[str, Any] | None = None,
        extract_term_matches_fn: Callable[[str, list[str]], tuple[list[str], list[str]]] | None = None,
        penalty_per_item: float | None = None,
        max_score_on_failure: float | None = None,
        llm_semantic_weight: float | None = None,
        max_llm_boost: float | None = None,
        match_high_threshold: float | None = None,
        **kwargs: Any,
    ) -> ComponentScoreResults:
        job_ctx = job if isinstance(job, JobEvaluationContext) else JobEvaluationContext.create(job)
        if extract_term_matches_fn is None:
            from app.services.scoring_engine import ScoringEngine

            extract_term_matches_fn = ScoringEngine._extract_term_matches

        typed_config = scoring_config if isinstance(scoring_config, ScoringConfig) else ScoringConfig.load(scoring_config if isinstance(scoring_config, dict) else None)

        penalty = penalty_per_item if penalty_per_item is not None else typed_config.penalty_per_item
        max_score_cap = max_score_on_failure if max_score_on_failure is not None else typed_config.max_score_on_failure
        high_threshold = match_high_threshold if match_high_threshold is not None else typed_config.match_high_threshold
        llm_weight = llm_semantic_weight if llm_semantic_weight is not None else typed_config.llm_semantic_weight
        max_boost = max_llm_boost if max_llm_boost is not None else typed_config.max_llm_boost

        params = RuleConfigManager.get_scoring_parameters()

        # 1. Role Score
        job_title = job_ctx.title
        role_score = params.default_role_score
        family_compatible = job_ctx.vac_family not in (None, "Unknown") and (
            TaxonomyClassifier.are_families_compatible(context.cand_families, job_ctx.vac_family)
            or any(_share_root_family(candidate_family, job_ctx.vac_family) for candidate_family in context.cand_families)
        )
        role_evidence_text = " ".join(
            [
                context.current_role or "",
                *context.experience_titles,
                context.domain_candidate_text or "",
            ]
        ).lower()
        role_evidence_tokens = set(re.findall(r"\w+", role_evidence_text))
        has_role_evidence = bool(job_ctx.title_lower) and (
            job_ctx.title_lower in role_evidence_text
            or (bool(job_ctx.title_words) and job_ctx.title_words.issubset(role_evidence_tokens))
        )
        if has_role_evidence:
            role_score = typed_config.perfect_component_score
        elif family_compatible:
            role_score = params.domain_default_match_score
        elif transition_detected:
            role_score = params.career_transition_role_score
        elif context.current_role and job_title:
            current_clean = context.current_role.strip().lower()
            if current_clean != job_ctx.title_lower and not common_words:
                role_score = params.role_divergence_score

        # 2. Skills Score
        req_skills = job_ctx.required_skills
        pref_keywords = job_ctx.preferred_keywords
        total_skills = len(req_skills) + len(pref_keywords)
        matched_total_skills = len(req_results.matched_skills) + len(req_results.matched_keywords)
        skills_score = None
        if total_skills > 0:
            skills_score = (matched_total_skills / total_skills) * 100.0

        # 3. Experience Score
        min_exp = job_ctx.min_experience_years
        max_exp = job_ctx.max_experience_years
        experience_score = None
        if min_exp is not None or max_exp is not None:
            matched_responsibilities, _ = extract_term_matches_fn(context.domain_candidate_text or context.norm_text, job_ctx.responsibilities)
            has_relevant_experience = _has_relevant_experience(context, job_ctx, matched_responsibilities)
            experience_score = typed_config.perfect_component_score if has_relevant_experience else 0.0
            
            relevant_exp = _calculate_relevant_experience(context, job_ctx, extract_term_matches_fn)
            
            if min_exp is not None and relevant_exp is not None and relevant_exp < min_exp:
                if min_exp > 0:
                    experience_score = (relevant_exp / min_exp) * params.below_min_exp_multiplier
                else:
                    experience_score = 0.0
                req_results.mandatory_failures.append(RequirementEvaluator._create_failure("MIN_EXPERIENCE_FAILED", "req_exp", f"Minimum Experience: {min_exp} years", f"Only {relevant_exp:.1f} years of relevant experience found.", penalty))
            if max_exp is not None and relevant_exp is not None and relevant_exp > max_exp:
                experience_score -= params.overqualification_penalty
            
            # If dates were unparseable, relevant_exp is None
            if relevant_exp is None and min_exp is not None:
                req_results.mandatory_failures.append(RequirementEvaluator._create_failure("EXPERIENCE_UNKNOWN", "req_exp", f"Minimum Experience: {min_exp} years", "Experience is UNKNOWN due to unparseable dates (requires manual review).", penalty))
                
            experience_score = max(0.0, min(typed_config.perfect_component_score, experience_score))

        # 4. Education Score
        education_req = job_ctx.education_requirements
        education_score = None
        if education_req:
            education_score = typed_config.perfect_component_score
            if not _education_requirement_matches(context, str(education_req), extract_term_matches_fn):
                education_score = 0.0

        # 5. Certification Score
        certification_req = job_ctx.certifications
        certification_score = None
        if certification_req:
            certification_score = typed_config.perfect_component_score
            from app.services.certification_resolver import CertificationResolver, CertificationMatchStatus

            cand_certs: list[str] = list(context.education_evidence)
            if context.optimized_profile and context.optimized_profile.certifications:
                cand_certs.extend(context.optimized_profile.certifications)
            if isinstance(context.resume_json, dict):
                cand_certs.extend(context.resume_json.get("certifications", []) or [])

            cert_outcome = CertificationResolver.match_certification(cand_certs, str(certification_req))
            if cert_outcome.status not in (CertificationMatchStatus.EXACT, CertificationMatchStatus.EQUIVALENT):
                certification_score = 0.0

        # 6. Domain Score (Pre-compiled Regex Matching)
        domain_score = None
        job_department = job_ctx.department
        if job_department:
            domain_score = params.domain_default_match_score
            if job_ctx.dept_term_patterns:
                matched_dept_terms = [p.pattern for p in job_ctx.dept_term_patterns if p.search(context.domain_candidate_text)]
                if matched_dept_terms:
                    domain_score = typed_config.perfect_component_score

        # 7. Technology Score
        technology_score = None
        tech_reqs = job_ctx.technologies
        if tech_reqs:
            tech_matched, _ = extract_term_matches_fn(context.norm_text, tech_reqs)
            technology_score = (len(tech_matched) / len(tech_reqs)) * typed_config.perfect_component_score

        # 8. Responsibilities Score
        responsibilities_score = None
        resp_reqs = job_ctx.responsibilities
        if resp_reqs:
            resp_matched, _ = extract_term_matches_fn(context.norm_text, resp_reqs)
            responsibilities_score = (len(resp_matched) / len(resp_reqs)) * typed_config.perfect_component_score

        # Calculate Overall Raw Score (Weighted)
        weights = typed_config.component_weights
        active_weights = 0.0
        weighted_sum = 0.0

        scores = [
            (role_score, weights["role"]),
            (skills_score, weights["skills"]),
            (experience_score, weights["experience"]),
            (education_score, weights["education"]),
            (domain_score, weights["domain"]),
            (technology_score, weights["technology"]),
            (certification_score, weights["certification"]),
            (responsibilities_score, weights["responsibilities"]),
        ]

        for score_val, weight in scores:
            if score_val is not None:
                weighted_sum += score_val * weight
                active_weights += weight

        raw_score = (weighted_sum / active_weights) if active_weights > 0 else 0.0
        total_weights_sum = sum(weights.values())
        component_coverage = (active_weights / total_weights_sum) if total_weights_sum > 0 else 0.0

        llm_boost = 0.0
        if llm_match and llm_match.semantic_fit_score:
            llm_boost = min(max_boost, llm_match.semantic_fit_score * llm_weight)

        raw_score += llm_boost

        if req_results.mandatory_failures:
            total_penalty = len(req_results.mandatory_failures) * penalty
            final_score = round(max(0.0, min(raw_score - total_penalty, max_score_cap)), 1)
            hr_review_required = True
            reason_str = "Mandatory requirement failure(s): " + "; ".join(f"{f.description} ({f.reason})" for f in req_results.mandatory_failures)
        else:
            final_score = round(min(100.0, max(0.0, raw_score)), 1)
            if final_score >= 100.0 and ((skills_score is not None and skills_score < 100.0) or len(req_results.missing_criteria) > 0 or (domain_score is not None and domain_score < 100.0)):
                final_score = params.false_positive_score_cap
            has_education_conflict = education_req is not None and education_score == 0.0
            hr_review_required = final_score < high_threshold or has_education_conflict
            reason_str = f"All mandatory requirements satisfied. Overall match score is {final_score}%."
            if has_education_conflict:
                reason_str += f" | Education mismatch requires HR review: vacancy requires '{education_req}'."

        # Penalty for keyword-only matches (0% skills match but high domain/other scores)
        zero_skills_cap = getattr(typed_config, "zero_skills_score_cap", getattr(params, "zero_skills_score_cap", 40.0))
        if skills_score is not None and skills_score == 0.0 and final_score > zero_skills_cap:
            final_score = min(final_score, zero_skills_cap)
            reason_str += f" | Capped score due to 0% skills match (keyword-only match, cap: {zero_skills_cap}%)."

        return ComponentScoreResults(
            role_score=role_score,
            skills_score=skills_score,
            experience_score=experience_score,
            education_score=education_score,
            domain_score=domain_score,
            technology_score=technology_score,
            certification_score=certification_score,
            responsibilities_score=responsibilities_score,
            component_coverage=component_coverage,
            raw_score=raw_score,
            final_score=final_score,
            hr_review_required=hr_review_required,
            reason_str=reason_str,
        )


class CrossDomainGuardEvaluator:
    """Evaluates taxonomy family compatibility and applies cross-domain score caps and mismatch penalties."""

    @staticmethod
    def _share_root_family(cand_family: str | None, vac_family: str | None) -> bool:
        """Returns True when vac_family is a named sub-team of cand_family (or vice-versa).

        Handles patterns such as:
          cand='Maintenance Team', vac='Maintenance Team - 1 (Ramesh Maurya)' -> True
          cand='Production Team',  vac='Maintenance Team - 1'                 -> False
        """
        return _share_root_family(cand_family, vac_family)

    @classmethod
    def evaluate(
        cls,
        context: CandidateAnalysisContext,
        job: JobEvaluationContext | dict[str, Any],
        initial_score: float,
        initial_domain_score: float | None,
        reason_str: str,
        mandatory_failures: list[MandatoryFailureDetails],
        **kwargs: Any,
    ) -> CrossDomainGuardResults:
        job_ctx = job if isinstance(job, JobEvaluationContext) else JobEvaluationContext.create(job)
        guard_params = RuleConfigManager.get_match_rules().cross_domain_guard

        vac_tax_domain, vac_family = job_ctx.vac_tax_domain, job_ctx.vac_family
        if (not vac_tax_domain or vac_tax_domain == "Unknown") and job_ctx.department:
            from app.repositories.department_domain import department_domain_repository
            dept_clean = job_ctx.department.strip().lower()
            for dom in department_domain_repository.get_all_domains():
                if dom.department_name and dom.department_name.strip().lower() == dept_clean:
                    vac_tax_domain = dom.domain_name
                    break

        is_tax_compat = TaxonomyClassifier.are_families_compatible(context.cand_families, vac_family)

        cand_domain = context.cand_tax_domain or context.cand_domain
        taxonomy_confident = context.taxonomy_confidence >= RuleConfigManager.get_taxonomy_rules().semantic_match_threshold
        is_same_canonical_domain = False
        if cand_domain and cand_domain != "Unknown" and vac_tax_domain and vac_tax_domain != "Unknown":
            if cand_domain.strip().lower() == vac_tax_domain.strip().lower():
                is_same_canonical_domain = True

        domain_mismatch = False
        if taxonomy_confident and not is_same_canonical_domain and vac_family not in (None, "Unknown") and context.cand_primary_family not in (None, "Unknown"):
            if not is_tax_compat:
                # Don't cap sub-families of the same root department
                if not cls._share_root_family(context.cand_primary_family, vac_family):
                    domain_mismatch = True
            elif context.cand_primary_family and vac_family:
                is_compat, status, score = DynamicTaxonomyService.check_family_compatibility(context.cand_primary_family, vac_family)
                compatibility_threshold = RuleConfigManager.get_taxonomy_rules().family_compatibility_min_score
                if (not is_compat or (score is not None and score < compatibility_threshold)) and not cls._share_root_family(context.cand_primary_family, vac_family):
                    domain_mismatch = True

        if taxonomy_confident and cand_domain and cand_domain != "Unknown" and vac_tax_domain and vac_tax_domain != "Unknown":
            cand_d_norm = cand_domain.strip().lower()
            vac_d_norm = vac_tax_domain.strip().lower()
            if not is_same_canonical_domain:
                def domain_groups(label: str) -> set[str]:
                    return {
                        group_name
                        for group_name, terms in guard_params.domain_guard_terms.items()
                        if group_name.lower() in label or any(term.lower() in label for term in terms)
                    }

                if not domain_groups(cand_d_norm).intersection(domain_groups(vac_d_norm)):
                    domain_mismatch = True

        # Software/IT candidate matched to a clearly non-IT vacancy: apply the
        # cross-domain cap even when taxonomy domain/family metadata is missing
        # ("Unknown").
        if context.is_software_cand and not is_tax_compat:
            req_skills_str = " ".join(job_ctx.required_skills) if job_ctx.required_skills else ""
            pref_kw_str = " ".join(job_ctx.preferred_keywords) if job_ctx.preferred_keywords else ""
            vacancy_evidence = " ".join([vac_tax_domain or "", job_ctx.department, job_ctx.title, req_skills_str, pref_kw_str])
            software_patterns = RuleConfigManager.get_compiled_cross_domain_guard()["software_requirement_patterns"]
            fallback_software_terms = ("engineer", "developer", "backend", "frontend", "fullstack", "python", "java", "c++", "c#", "javascript", "typescript", "react", "node", "code", "software", "api", "tech", "data", "cloud", "devops")
            is_software_vacancy = (
                job_ctx.has_software_req
                or any(pattern.search(vacancy_evidence) for pattern in software_patterns)
                or any(term in vacancy_evidence.lower() for term in fallback_software_terms)
            )
            if not is_software_vacancy:
                domain_mismatch = True

        final_score = initial_score
        domain_score = initial_domain_score
        additional_failures: list[MandatoryFailureDetails] = []

        if domain_mismatch:
            domain_score = 0.0
            final_score = round(
                max(
                    0.0,
                    min(
                        final_score * guard_params.domain_mismatch_multiplier,
                        guard_params.domain_mismatch_score_cap,
                    ),
                ),
                1,
            )
            reason_str += f" | Strict Domain Mismatch Penalty: Candidate domain ({context.cand_tax_domain}) conflicts with vacancy domain ({vac_tax_domain})."
            if not any(f.requirement_id == "req_domain_mismatch" for f in mandatory_failures):
                additional_failures.append(
                    MandatoryFailureDetails(
                        failure_code="DOMAIN_MISMATCH",
                        requirement_id="req_domain_mismatch",
                        description=f"Domain Mismatch: Candidate family ({context.cand_primary_family or 'Unknown'}) conflicts with vacancy family ({vac_family})",
                        reason=f"Candidate job family ({context.cand_primary_family or 'Unknown'}) is incompatible with target job family ({vac_family}).",
                        score_impact=guard_params.mandatory_failure_score_impact,
                    )
                )

        is_domain_capped = domain_mismatch or any(f.requirement_id == "req_domain_mismatch" for f in mandatory_failures) or bool(additional_failures)

        domain_capped_reason = None
        if is_domain_capped:
            domain_capped_reason = f"Strict domain mismatch penalty applied. Candidate domain ({context.cand_tax_domain}) conflicts with vacancy domain ({vac_tax_domain})."

        return CrossDomainGuardResults(
            final_score=final_score,
            domain_score=domain_score,
            reason_str=reason_str,
            is_domain_capped=is_domain_capped,
            domain_capped_reason=domain_capped_reason,
            vac_tax_domain=vac_tax_domain,
            vac_family=vac_family,
            additional_mandatory_failures=additional_failures,
        )


class RecommendationEvaluator:
    """Determines match classification, recommendation string, and confidence score."""

    @staticmethod
    def _calculate_confidence_score(total_req_count: int, evidence_count: int) -> float:
        """Isolated confidence score calculation helper."""
        if total_req_count > 0:
            return round(evidence_count / total_req_count, 2)
        return 1.0

    @classmethod
    def evaluate(
        cls,
        final_score: float,
        component_coverage: float | None = None,
        total_req_count: int = 0,
        evidence_count: int = 0,
        scoring_config: ScoringConfig | dict[str, Any] | None = None,
        reason_str: str = "",
        missing_criteria: list[str] | None = None,
        coverage: float | None = None,
        match_high_threshold: float | None = None,
        match_medium_threshold: float | None = None,
        **kwargs: Any,
    ) -> RecommendationResults:
        recs = RuleConfigManager.get_recommendations()

        cov = component_coverage if component_coverage is not None else (coverage if coverage is not None else 1.0)
        missing = missing_criteria if missing_criteria is not None else []
        typed_config = scoring_config if isinstance(scoring_config, ScoringConfig) else ScoringConfig.load(scoring_config if isinstance(scoring_config, dict) else None)
        high_thresh = match_high_threshold if match_high_threshold is not None else typed_config.match_high_threshold
        med_thresh = match_medium_threshold if match_medium_threshold is not None else typed_config.match_medium_threshold
        low_coverage_threshold = RuleConfigManager.get_scoring_parameters().low_coverage_threshold

        if cov < low_coverage_threshold:
            classification = "LOW"
            recommendation = recs.low_coverage
        elif final_score >= high_thresh:
            classification = "HIGH"
            recommendation = recs.high_match
        elif final_score >= med_thresh:
            classification = "MEDIUM"
            recommendation = recs.medium_match
        else:
            classification = "LOW"
            recommendation = recs.low_match

        confidence_val = cls._calculate_confidence_score(total_req_count, evidence_count)

        if cov < low_coverage_threshold:
            missing.append("LOW_COVERAGE: Vacancy has poorly defined requirements.")
            reason_str = f"{reason_str} | Note: Low match coverage ({int(cov * 100)}%)."

        return RecommendationResults(
            classification=classification,
            recommendation=recommendation,
            confidence_val=confidence_val,
            reason_str=reason_str,
        )


class VacancyMatchStatus(str, Enum):
    MATCHED = "MATCHED"
    POTENTIAL_MATCH = "POTENTIAL_MATCH"
    NO_STRONG_MATCH = "NO_STRONG_MATCH"
    NO_ACTIVE_VACANCIES = "NO_ACTIVE_VACANCIES"
    ANALYSIS_NOT_AVAILABLE = "ANALYSIS_NOT_AVAILABLE"
    ANALYSIS_UNAVAILABLE = "ANALYSIS_UNAVAILABLE"
    PROCESSING = "PROCESSING"
    FAILED = "FAILED"


@dataclass
class VacancyFitResults:
    vacancy_fit_score: float
    score_breakdown: Any  # VacancyFitScoreBreakdown
    match_status: str  # "MATCHED", "POTENTIAL_MATCH", or "NO_STRONG_VACANCY_MATCH"
    reason: str


class VacancyFitEvaluator:
    """
    Evaluates candidate suitability against an open vacancy using structured hierarchy + semantic fit.

    Weighted Scoring Dimensions:
    1. Hierarchy Fit (25%): MainDeptID, DeptID, DesigID alignment
    2. Designation/Role Fit (20%): Position title and job family alignment
    3. Skills Fit (25%): Mandatory & preferred technical & functional skills
    4. Experience Fit (15%): Total & relevant years of experience
    5. Semantic Similarity (15%): Dense vector nomic-embed-text similarity score
    """

    @classmethod
    def evaluate_fit(
        cls,
        context: CandidateAnalysisContext,
        job: JobEvaluationContext,
        cv_text: str = "",
        cand_hierarchy: Any | None = None,
        comp_results: Any | None = None,
        mandatory_failures: list[MandatoryFailureDetails] | None = None,
        scoring_config: Any | None = None,
        threshold: float | None = None,
        llm_boost: float = 0.0,
    ) -> VacancyFitResults:
        from app.schemas.match import VacancyFitScoreBreakdown
        from app.services.embedding_service import EmbeddingService

        typed_config = scoring_config if isinstance(scoring_config, ScoringConfig) else ScoringConfig.load(scoring_config if isinstance(scoring_config, dict) else None)
        params = RuleConfigManager.get_scoring_parameters()
        threshold = threshold if threshold is not None else typed_config.match_high_threshold
        raw_job = job.raw_job or {}

        # 1. Vacancy Hierarchy IDs
        v_main_id = raw_job.get("main_department_id") if raw_job.get("main_department_id") is not None else raw_job.get("MainDeptID")
        v_dept_id = raw_job.get("department_id") if raw_job.get("department_id") is not None else raw_job.get("DeptID")
        v_desig_id = raw_job.get("designation_id") if raw_job.get("designation_id") is not None else raw_job.get("DesigID")

        # Candidate Hierarchy IDs
        c_main_id = getattr(cand_hierarchy.main_department, "id", None) if cand_hierarchy and hasattr(cand_hierarchy, "main_department") else None
        c_dept_id = getattr(cand_hierarchy.department, "id", None) if cand_hierarchy and hasattr(cand_hierarchy, "department") else None
        c_desig_id = getattr(cand_hierarchy.designation, "id", None) if cand_hierarchy and hasattr(cand_hierarchy, "designation") else None

        # 1. Hierarchy Fit Score (0-100)
        hierarchy_score = 0.0
        hierarchy_mismatch = False

        if v_main_id is None or c_main_id is None:
            hierarchy_score = params.domain_default_match_score
        elif c_main_id is not None and int(c_main_id) == int(v_main_id):
            hierarchy_score = params.domain_default_match_score
            if v_dept_id is not None and c_dept_id is not None and int(c_dept_id) == int(v_dept_id):
                hierarchy_score = (params.domain_default_match_score + typed_config.perfect_component_score) / 2.0
                if v_desig_id is not None and c_desig_id is not None and int(c_desig_id) == int(v_desig_id):
                    hierarchy_score = typed_config.perfect_component_score
        else:
            hierarchy_score = 0.0
            hierarchy_mismatch = True

        is_valid_h = getattr(cand_hierarchy, "is_hierarchy_valid", True) if cand_hierarchy else True
        if is_valid_h is False:
            hierarchy_mismatch = True

        hierarchy_penalty = max(0.0, typed_config.perfect_component_score - typed_config.match_high_threshold) if hierarchy_mismatch else 0.0

        # 2. Designation / Role Fit Score (0-100)
        role_score = 0.0
        if comp_results and hasattr(comp_results, "role_score"):
            role_score = float(comp_results.role_score or 0.0)
        else:
            role_score = params.domain_default_match_score

        # 3. Skills Fit Score (0-100)
        skills_score = 0.0
        if comp_results and hasattr(comp_results, "skills_score"):
            skills_score = float(comp_results.skills_score or 0.0)
        else:
            skills_score = params.domain_default_match_score

        # 4. Experience Fit Score (0-100)
        cand_exp = float(getattr(context, "candidate_experience", 0.0) or 0.0)
        min_exp = float(getattr(job, "min_experience_years", None) or getattr(job, "min_experience", 0.0) or 0.0)
        max_exp = getattr(job, "max_experience_years", None)
        experience_score = 0.0
        if comp_results and hasattr(comp_results, "experience_score"):
            experience_score = float(comp_results.experience_score or 0.0)
        else:
            if cand_exp >= min_exp:
                experience_score = typed_config.perfect_component_score
            else:
                experience_score = max(0.0, (cand_exp / min_exp) * params.below_min_exp_multiplier if min_exp > 0 else 0.0)
            if max_exp is not None and cand_exp > max_exp:
                experience_score = max(0.0, experience_score - params.overqualification_penalty)

        resps = getattr(job, "responsibilities", []) or []
        j_title = getattr(job, "title", "") or ""
        j_dept = getattr(job, "department", "") or ""
        vac_desc = str(raw_job.get("job_description") or raw_job.get("description") or " ".join(resps) or j_title)
        vac_text = f"Title: {j_title}. Department: {j_dept}. Description: {vac_desc[:300]}"
        cand_text = str(getattr(context, "domain_candidate_text", None) or cv_text or "")

        cand_vector: list[float] | None = None
        vac_vector: list[float] | None = None
        try:
            from app.core.config import settings
            j_id = str(getattr(job, "job_id", "") or "")
            cand_vector = EmbeddingService.generate_embedding(cand_text, model_version=settings.EMBEDDING_MODEL, identifier=f"cand_fit_prof:{hash(cand_text)}")
            vac_vector = EmbeddingService.generate_embedding(vac_text, model_version=settings.EMBEDDING_MODEL, identifier=f"vac_fit_prof:{j_id}:{hash(vac_text)}")
        except Exception:
            pass

        if cand_vector and vac_vector:
            sim = max(0.0, min(1.0, float(EmbeddingService.cosine_similarity(cand_vector, vac_vector))))
            semantic_score = round(sim * 100.0, 1)
        else:
            semantic_score = float(getattr(comp_results, "responsibilities_score", params.domain_default_match_score) or params.domain_default_match_score)

        weights = typed_config.component_weights
        skill_weight = weights.get("skills", 0.0) + weights.get("technology", 0.0)
        semantic_weight = weights.get("responsibilities", 0.0)
        education_score = float(getattr(comp_results, "education_score", 0.0) or 0.0) if getattr(job, "education_requirements", None) else 0.0
        fit_components = [
            (hierarchy_score, weights.get("domain", 0.0), bool(j_dept or v_main_id is not None)),
            (role_score, weights.get("role", 0.0), bool(j_title)),
            (
                skills_score,
                skill_weight,
                bool(
                    getattr(job, "required_skills", None)
                    or getattr(job, "preferred_keywords", None)
                    or getattr(job, "technologies", None)
                ),
            ),
            (
                experience_score,
                weights.get("experience", 0.0),
                getattr(job, "min_experience_years", None) is not None or getattr(job, "max_experience_years", None) is not None,
            ),
            (education_score, weights.get("education", 0.0), bool(getattr(job, "education_requirements", None))),
            (semantic_score, semantic_weight, bool(vac_desc)),
        ]
        active_weight = sum(weight for _, weight, active in fit_components if active and weight > 0.0)
        weighted_score = sum(score * weight for score, weight, active in fit_components if active and weight > 0.0)
        raw_fit_score = (weighted_score / active_weight if active_weight > 0.0 else 0.0) + llm_boost

        # Guardrail: High embedding similarity CANNOT override wrong department / invalid hierarchy
        hard_failures = list(mandatory_failures or [])
        if min_exp > 0 and cand_exp < min_exp and not any(
            str(getattr(failure, "requirement_id", "") or (failure.get("requirement_id") if isinstance(failure, dict) else "")) == "minimum_experience"
            for failure in hard_failures
        ):
            hard_failures.append(
                {
                    "requirement_id": "minimum_experience",
                    "reason": f"Candidate has {cand_exp:.1f} years; vacancy requires {min_exp:.1f} years.",
                }
            )
        rejection_cap = typed_config.calculate_rejection_cap()
        if hard_failures:
            final_fit_score = round(min(rejection_cap, max(0.0, raw_fit_score)), 1)
            match_status = "NO_STRONG_VACANCY_MATCH"
            reason = f"Mandatory requirement failure(s): {len(hard_failures)} hard gate(s) failed; vacancy fit capped at {final_fit_score:.1f}/100."
        elif hierarchy_mismatch:
            mismatch_cap = min(typed_config.max_score_on_failure, rejection_cap)
            final_fit_score = round(min(mismatch_cap, max(0.0, raw_fit_score - hierarchy_penalty)), 1)
            match_status = "NO_STRONG_VACANCY_MATCH"
            reason = f"Vacancy fit rejected ({final_fit_score:.1f}/100): Main Department or hierarchy mismatch."
        elif raw_fit_score < typed_config.match_medium_threshold:
            final_fit_score = round(raw_fit_score, 1)
            match_status = "NO_STRONG_VACANCY_MATCH"
            reason = f"Vacancy fit score ({final_fit_score:.1f}/100) below potential-match threshold ({typed_config.match_medium_threshold:.1f})."
        elif raw_fit_score < threshold:
            final_fit_score = round(raw_fit_score, 1)
            match_status = "POTENTIAL_MATCH"
            reason = f"Potential vacancy fit ({final_fit_score:.1f}/100) below strong-match threshold ({threshold:.1f}); HR review required."
        else:
            final_fit_score = round(raw_fit_score, 1)
            match_status = "MATCHED"
            reason = f"Strong vacancy fit ({final_fit_score:.1f}/100): Valid hierarchy and skills alignment."

        breakdown = VacancyFitScoreBreakdown(
            hierarchy_score=round(hierarchy_score, 1),
            designation_role_score=round(role_score, 1),
            skills_score=round(skills_score, 1),
            experience_score=round(experience_score, 1),
            education_score=round(education_score, 1),
            semantic_similarity_score=round(semantic_score, 1),
            overall_fit_score=final_fit_score,
            hierarchy_mismatch_penalty=round(hierarchy_penalty, 1),
            is_hierarchy_valid=is_valid_h,
            match_status=match_status,
        )

        return VacancyFitResults(
            vacancy_fit_score=final_fit_score,
            score_breakdown=breakdown,
            match_status=match_status,
            reason=reason,
        )

    @classmethod
    def _parse_score_value(cls, value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    @classmethod
    def resolve_opening_score(
        cls,
        opening: dict[str, Any] | Any,
        scoring_config: ScoringConfig | None = None,
    ) -> float:
        """Resolve the canonical score while remaining compatible with legacy persisted matches."""
        if isinstance(opening, dict):
            fit_score = cls._parse_score_value(opening.get("vacancy_fit_score"))
            score_breakdown = opening.get("score_breakdown")
            overall_score = opening.get("overall_score")
            legacy_score = opening.get("score")
        else:
            fit_score = cls._parse_score_value(getattr(opening, "vacancy_fit_score", None))
            score_breakdown = getattr(opening, "score_breakdown", None)
            overall_score = getattr(opening, "overall_score", None)
            legacy_score = getattr(opening, "score", None)

        if fit_score is not None and (fit_score != 0.0 or score_breakdown is not None):
            final_resolved_score = float(fit_score)
        else:
            fallback_score = cls._parse_score_value(overall_score)
            if fallback_score is None:
                fallback_score = cls._parse_score_value(legacy_score)
            final_resolved_score = float(fallback_score if fallback_score is not None else fit_score or 0.0)

        # Normalize legacy contradictory results (high score + rejection status)
        status = cls.classify_opening_fit(opening)
        if status == VacancyMatchStatus.NO_STRONG_MATCH.value:
            cfg = scoring_config if isinstance(scoring_config, ScoringConfig) else ScoringConfig.load()
            cap = cfg.calculate_rejection_cap()
            if final_resolved_score > cap:
                return float(cap)
                
        return final_resolved_score

    @classmethod
    def classify_opening_fit(
        cls,
        opening: dict[str, Any] | Any,
        high_threshold: float | None = None,
        potential_threshold: float | None = None,
    ) -> str:
        """
        Canonical evaluator classification for an individual vacancy opening/match result.
        Returns the canonical match status generated at scoring time.
        Does not recalculate.
        """
        if not opening:
            return VacancyMatchStatus.NO_STRONG_MATCH.value

        if isinstance(opening, dict):
            status = str(opening.get("vacancy_match_status") or opening.get("match_status") or "").upper()
        else:
            status = str(getattr(opening, "vacancy_match_status", getattr(opening, "match_status", ""))).upper()

        if status in {"MATCHED", "POTENTIAL_MATCH", "NO_STRONG_MATCH"}:
            return status

        # Legacy compatibility fallback for historical records / test fixtures without canonical status
        if isinstance(opening, dict):
            classification = str(opening.get("classification") or "").upper()
            recommendation = str(opening.get("recommendation") or "").upper()
            score_val = cls._parse_score_value(opening.get("score") or opening.get("overall_score") or opening.get("vacancy_fit_score"))
        else:
            classification = str(getattr(opening, "classification", "") or "").upper()
            recommendation = str(getattr(opening, "recommendation", "") or "").upper()
            score_val = cls._parse_score_value(getattr(opening, "score", None) or getattr(opening, "overall_score", None) or getattr(opening, "vacancy_fit_score", None))

        if high_threshold is not None and score_val is not None and score_val < high_threshold:
            if potential_threshold is not None and score_val >= potential_threshold:
                return VacancyMatchStatus.POTENTIAL_MATCH.value
            return VacancyMatchStatus.NO_STRONG_MATCH.value

        if classification == "HIGH" or recommendation in {"STRONG_MATCH", "HIGH_MATCH"}:
            return VacancyMatchStatus.MATCHED.value
        if classification == "MEDIUM" or recommendation in {"POTENTIAL_MATCH", "MEDIUM_MATCH"}:
            return VacancyMatchStatus.POTENTIAL_MATCH.value

        return VacancyMatchStatus.NO_STRONG_MATCH.value

    @classmethod
    def is_eligible_match(
        cls,
        opening: dict[str, Any] | Any,
        high_threshold: float | None = None,
        potential_threshold: float | None = None,
    ) -> bool:
        """Returns True only for a verified canonical MATCHED result.

        POTENTIAL_MATCH results remain available for manual HR review, but are
        never promoted into suitable_openings.
        """
        fit = cls.classify_opening_fit(opening, high_threshold=high_threshold, potential_threshold=potential_threshold)
        return fit == VacancyMatchStatus.MATCHED.value

    @classmethod
    def determine_candidate_match_status(
        cls,
        candidate_id: str,
        result_data: dict[str, Any] | None,
        vacancies_evaluated: list[dict[str, Any] | Any] | None,
        has_active_vacancies: bool = True,
        high_threshold: float | None = None,
        potential_threshold: float | None = None,
    ) -> str:
        """
        Canonical source of truth for candidate-level match decision status.
        Returns one of:
          - ANALYSIS_NOT_AVAILABLE
          - PROCESSING
          - FAILED
          - NO_ACTIVE_VACANCIES
          - MATCHED
          - POTENTIAL_MATCH
          - NO_STRONG_MATCH
        """
        if result_data is None or not isinstance(result_data, dict):
            return VacancyMatchStatus.ANALYSIS_NOT_AVAILABLE.value

        if high_threshold is None or potential_threshold is None:
            scoring_config = ScoringConfig.load()
            high_threshold = high_threshold if high_threshold is not None else scoring_config.match_high_threshold
            potential_threshold = potential_threshold if potential_threshold is not None else scoring_config.match_medium_threshold

        proc_status = str(result_data.get("status") or "").lower()
        result_match_status = str(result_data.get("match_status") or "").upper()
        if proc_status == "analysis_unavailable" or result_match_status == VacancyMatchStatus.ANALYSIS_UNAVAILABLE.value:
            return VacancyMatchStatus.ANALYSIS_UNAVAILABLE.value
        if proc_status == "processing":
            return VacancyMatchStatus.PROCESSING.value
        if proc_status in {"failed", "error"}:
            return VacancyMatchStatus.FAILED.value

        if not has_active_vacancies:
            return VacancyMatchStatus.NO_ACTIVE_VACANCIES.value

        openings = vacancies_evaluated or []
        if not openings:
            return VacancyMatchStatus.NO_STRONG_MATCH.value

        statuses = [
            cls.classify_opening_fit(o, high_threshold=high_threshold, potential_threshold=potential_threshold)
            for o in openings
        ]

        if VacancyMatchStatus.MATCHED.value in statuses:
            return VacancyMatchStatus.MATCHED.value
        elif VacancyMatchStatus.POTENTIAL_MATCH.value in statuses:
            return VacancyMatchStatus.POTENTIAL_MATCH.value
        else:
            return VacancyMatchStatus.NO_STRONG_MATCH.value
