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

_stop_phrases_cache: frozenset[str] | None = None


def _stop_phrases() -> frozenset[str]:
    global _stop_phrases_cache
    if _stop_phrases_cache is None:
        _stop_phrases_cache = RuleConfigManager.get_term_matching_assets()["stop_phrases"]
    return _stop_phrases_cache


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


def _has_relevant_experience(
    context: CandidateAnalysisContext,
    job: JobEvaluationContext,
    matched_responsibilities: list[str] | None = None,
) -> bool:
    """Return whether verified experience is relevant to the vacancy evidence."""
    if context.candidate_experience is None or context.candidate_experience <= 0:
        return False

    if job.vac_family not in (None, "Unknown") and TaxonomyClassifier.are_families_compatible(context.cand_families, job.vac_family):
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

    return False


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
    def _create_evidence(cv_ev: str, vac_ev: str) -> DualEvidence:
        return DualEvidence(cv_evidence=cv_ev, vacancy_evidence=vac_ev)

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
        req_id: str,
        desc: str,
        reason: str,
        penalty: float,
    ) -> MandatoryFailureDetails:
        return MandatoryFailureDetails(
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
        pref_keywords = job_ctx.preferred_keywords
        min_exp = job_ctx.min_experience_years
        max_exp = job_ctx.max_experience_years
        max_ctc = job_ctx.max_ctc
        education_req = job_ctx.education_requirements
        certification_req = job_ctx.certifications

        # 1. Mandatory Skills
        matched_skills, missing_skills = extract_term_matches_fn(context.norm_text, req_skills)
        if llm_match and llm_match.matched_skills:
            for ms in llm_match.matched_skills:
                if ms not in matched_skills:
                    matched_skills.append(ms)
                if ms in missing_skills:
                    missing_skills.remove(ms)

        results.matched_skills = matched_skills
        results.missing_skills = missing_skills

        matched_responsibilities, _ = extract_term_matches_fn(context.domain_candidate_text or context.norm_text, job_ctx.responsibilities)
        has_relevant_experience = _has_relevant_experience(context, job_ctx, matched_responsibilities)

        for skill in req_skills:
            if is_ignorable_requirement(skill):
                continue
            req_id = f"req_skill_{skill.lower().replace(' ', '_')}"
            vac_ev = f"Mandatory Skill Requirement: {skill}"
            if skill in matched_skills:
                cv_ev = f"CV contains skill: '{skill}'"
                ev = cls._create_evidence(cv_ev, vac_ev)
                results.mandatory_reqs.append(
                    cls._create_requirement(
                        req_id,
                        f"Skill: {skill}",
                        RequirementTier.MANDATORY,
                        RequirementStatus.SATISFIED,
                        ev,
                    )
                )
                results.evidence_map[req_id] = ev
                results.matched_criteria.append(f"Skill ({skill})")
            else:
                cv_ev = f"CV missing required skill: '{skill}'"
                ev = cls._create_evidence(cv_ev, vac_ev)
                reason = f"Candidate CV lacks documented skill '{skill}'."
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
                results.mandatory_failures.append(cls._create_failure(req_id, f"Mandatory Skill: {skill}", reason, penalty))
                results.missing_criteria.append(f"Mandatory Skill ({skill})")

        # 2. Preferred Keywords
        matched_keywords, missing_keywords = extract_term_matches_fn(context.norm_text, pref_keywords)
        results.matched_keywords = matched_keywords
        results.missing_keywords = missing_keywords

        for kw in pref_keywords:
            req_id = f"req_pref_{kw.lower().replace(' ', '_')}"
            vac_ev = f"Preferred Keyword Requirement: {kw}"
            if kw in matched_keywords:
                cv_ev = f"CV contains preferred keyword: '{kw}'"
                ev = cls._create_evidence(cv_ev, vac_ev)
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
            if has_relevant_experience and context.candidate_experience is not None and context.candidate_experience >= min_exp:
                cv_ev = f"Candidate experience {context.candidate_experience} years meets minimum requirement ({min_exp} years)"
                ev = cls._create_evidence(cv_ev, vac_ev)
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
            else:
                exp_val = context.candidate_experience if context.candidate_experience is not None else 0.0
                cv_ev = f"Candidate experience {exp_val} years is below minimum required ({min_exp} years)"
                reason = (
                    f"Candidate experience ({exp_val} yrs) is not relevant to the vacancy domain or responsibilities."
                    if context.candidate_experience is not None and context.candidate_experience >= min_exp and not has_relevant_experience
                    else f"Candidate experience ({exp_val} yrs) is less than required minimum ({min_exp} yrs)."
                )
                ev = cls._create_evidence(cv_ev, vac_ev)
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
                results.mandatory_failures.append(cls._create_failure(req_id, f"Min Experience: {min_exp} years", reason, penalty))
                results.missing_criteria.append(f"Min Experience ({min_exp} years)")

        # SENIORITY GATE: Reject overqualified candidates for junior roles
        if max_exp is not None and context.candidate_experience is not None:
            req_id = "req_seniority_gate"
            vac_ev = f"Seniority Gate (Max Exp: {max_exp} yrs)"
            seniority_buffer = 2.0 # Allow up to 2 years over qualification before hard rejecting
            if context.candidate_experience <= (max_exp + seniority_buffer):
                cv_ev = f"Candidate experience {context.candidate_experience} years is within allowable seniority bounds (max {max_exp} yrs + {seniority_buffer} yrs buffer)"
                ev = cls._create_evidence(cv_ev, vac_ev)
                results.mandatory_reqs.append(
                    cls._create_requirement(
                        req_id,
                        f"Seniority Bound: {max_exp} years",
                        RequirementTier.MANDATORY,
                        RequirementStatus.SATISFIED,
                        ev,
                    )
                )
                results.evidence_map[req_id] = ev
                results.matched_criteria.append(f"Seniority Gate (Max {max_exp} years)")
            else:
                cv_ev = f"Candidate experience {context.candidate_experience} years significantly exceeds maximum {max_exp} years"
                reason = f"Candidate seniority level is fundamentally incompatible with the vacancy (overqualified by {context.candidate_experience - max_exp:.1f} years)."
                ev = cls._create_evidence(cv_ev, vac_ev)
                results.mandatory_reqs.append(
                    cls._create_requirement(
                        req_id,
                        f"Seniority Bound: {max_exp} years",
                        RequirementTier.MANDATORY,
                        RequirementStatus.FAILED,
                        ev,
                        failure_reason=reason,
                    )
                )
                results.evidence_map[req_id] = ev
                results.mandatory_failures.append(cls._create_failure(req_id, f"Seniority Gate: Max {max_exp} years", reason, penalty))
                results.missing_criteria.append(f"Seniority Gate (Max {max_exp} years)")

        # 4. Mandatory Education
        if education_req:
            req_id = "req_education"
            vac_ev = f"Mandatory Education Requirement: {education_req}"
            edu_matched, _ = extract_term_matches_fn(context.norm_text, [str(education_req)])
            profile_education = " ".join(context.optimized_profile.education_domains) if context.optimized_profile else ""
            profile_edu_matched, _ = extract_term_matches_fn(profile_education.lower(), [str(education_req)]) if profile_education else ([], [])
            has_profile_edu = bool(profile_edu_matched)
            if edu_matched or has_profile_edu:
                cv_ev = f"CV satisfies education requirement: '{education_req}'"
                ev = cls._create_evidence(cv_ev, vac_ev)
                results.mandatory_reqs.append(
                    cls._create_requirement(
                        req_id,
                        f"Education: {education_req}",
                        RequirementTier.MANDATORY,
                        RequirementStatus.SATISFIED,
                        ev,
                    )
                )
                results.evidence_map[req_id] = ev
                results.matched_criteria.append(f"Education ({education_req})")
            else:
                cv_ev = f"CV missing education requirement: '{education_req}'"
                ev = cls._create_evidence(cv_ev, vac_ev)
                reason = f"Candidate CV lacks documented education requirement '{education_req}'."
                results.mandatory_reqs.append(
                    cls._create_requirement(
                        req_id,
                        f"Education: {education_req}",
                        RequirementTier.MANDATORY,
                        RequirementStatus.FAILED,
                        ev,
                        failure_reason=reason,
                    )
                )
                results.evidence_map[req_id] = ev
                results.mandatory_failures.append(cls._create_failure(req_id, f"Mandatory Education: {education_req}", reason, penalty))
                results.missing_criteria.append(f"Mandatory Education ({education_req})")

        # 5. Mandatory Certification
        if certification_req:
            req_id = "req_certification"
            vac_ev = f"Mandatory Certification Requirement: {certification_req}"
            cert_matched, _ = extract_term_matches_fn(context.norm_text, [str(certification_req)])
            has_profile_cert = bool(context.optimized_profile and context.optimized_profile.certifications)
            if cert_matched or has_profile_cert:
                cv_ev = f"CV satisfies certification requirement: '{certification_req}'"
                ev = cls._create_evidence(cv_ev, vac_ev)
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
                cv_ev = f"CV missing certification requirement: '{certification_req}'"
                ev = cls._create_evidence(cv_ev, vac_ev)
                reason = f"Candidate CV lacks required certification '{certification_req}'."
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
            ev = cls._create_evidence(cv_ev, vac_ev)
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
            results.mandatory_failures.append(cls._create_failure(req_id, f"Max CTC Budget: {max_ctc}", reason, penalty))
            results.missing_criteria.append(f"Max CTC Budget ({max_ctc})")

        # 7. Preferred Upper Experience Limit
        if max_exp is not None and context.candidate_experience is not None and has_relevant_experience:
            req_id = "req_max_experience"
            vac_ev = f"Preferred Upper Experience Limit: {max_exp} years"
            if context.candidate_experience <= max_exp:
                cv_ev = f"Candidate experience {context.candidate_experience} years is within preferred upper bound ({max_exp} years)"
                ev = cls._create_evidence(cv_ev, vac_ev)
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
                ev = cls._create_evidence(cv_ev, vac_ev)
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
        if transition_detected:
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
            if has_relevant_experience and min_exp is not None and context.candidate_experience is not None and context.candidate_experience < min_exp:
                if min_exp > 0:
                    experience_score = (context.candidate_experience / min_exp) * params.below_min_exp_multiplier
                else:
                    experience_score = 0.0
            if has_relevant_experience and max_exp is not None and context.candidate_experience is not None and context.candidate_experience > max_exp:
                experience_score -= params.overqualification_penalty
            experience_score = max(0.0, min(typed_config.perfect_component_score, experience_score))

        # 4. Education Score
        education_req = job_ctx.education_requirements
        education_score = None
        if education_req:
            education_score = typed_config.perfect_component_score
            edu_matched, _ = extract_term_matches_fn(context.norm_text, [str(education_req)])
            profile_education = " ".join(context.optimized_profile.education_domains) if context.optimized_profile else ""
            profile_edu_matched, _ = extract_term_matches_fn(profile_education.lower(), [str(education_req)]) if profile_education else ([], [])
            if not edu_matched and not profile_edu_matched:
                education_score = 0.0

        # 5. Certification Score
        certification_req = job_ctx.certifications
        certification_score = None
        if certification_req:
            certification_score = typed_config.perfect_component_score
            cert_matched, _ = extract_term_matches_fn(context.norm_text, [str(certification_req)])
            if not cert_matched and not (context.optimized_profile and context.optimized_profile.certifications):
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
            hr_review_required = final_score < high_threshold
            reason_str = f"All mandatory requirements satisfied. Overall match score is {final_score}%."

        # Penalty for keyword-only matches (0% skills match but high domain/other scores)
        if skills_score is not None and skills_score == 0.0 and final_score > 40.0:
            final_score = min(final_score, 40.0)
            reason_str += " | Capped score due to 0% skills match (keyword-only match)."

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

        domain_mismatch = False
        if vac_family not in (None, "Unknown") and context.cand_primary_family not in (None, "Unknown"):
            if not is_tax_compat:
                domain_mismatch = True
            elif context.cand_primary_family and vac_family:
                is_compat, status, score = DynamicTaxonomyService.check_family_compatibility(context.cand_primary_family, vac_family)
                if not is_compat or (score is not None and score < 0.4):
                    domain_mismatch = True
        cand_domain = context.cand_domain or context.cand_tax_domain
        if cand_domain and cand_domain != "Unknown" and vac_tax_domain and vac_tax_domain != "Unknown":
            if cand_domain.strip().lower() != vac_tax_domain.strip().lower():
                domain_mismatch = True

        # Software/IT candidate matched to a clearly non-IT vacancy: apply the
        # cross-domain cap even when taxonomy domain/family metadata is missing
        # ("Unknown").
        if context.is_software_cand and not is_tax_compat:
            is_it_vacancy = False
            if vac_tax_domain and vac_tax_domain != "Unknown":
                is_it_vacancy = (vac_tax_domain.lower() == "information technology" or vac_tax_domain.lower() == "cis team")
            elif job_ctx.department:
                is_it_vacancy = (job_ctx.department.lower() == "cis team" or job_ctx.department.lower() == "information technology")
                
            if not job_ctx.has_software_req and not is_it_vacancy:
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

        if cov < 0.5:
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

        if cov < 0.5:
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
        scoring_config: Any | None = None,
        threshold: float = 60.0,
    ) -> VacancyFitResults:
        from app.schemas.match import VacancyFitScoreBreakdown
        from app.services.embedding_service import EmbeddingService

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

        if v_main_id is None:
            hierarchy_score = 70.0
        elif c_main_id is not None and int(c_main_id) == int(v_main_id):
            hierarchy_score = 60.0
            if v_dept_id is not None and c_dept_id is not None and int(c_dept_id) == int(v_dept_id):
                hierarchy_score = 80.0
                if v_desig_id is not None and c_desig_id is not None and int(c_desig_id) == int(v_desig_id):
                    hierarchy_score = 100.0
        else:
            hierarchy_score = 0.0
            hierarchy_mismatch = True

        is_valid_h = getattr(cand_hierarchy, "is_hierarchy_valid", True) if cand_hierarchy else True
        if is_valid_h is False:
            hierarchy_mismatch = True

        hierarchy_penalty = 35.0 if hierarchy_mismatch else 0.0

        # 2. Designation / Role Fit Score (0-100)
        role_score = 0.0
        if comp_results and hasattr(comp_results, "role_score"):
            role_score = float(comp_results.role_score or 0.0)
        else:
            role_score = 50.0

        # 3. Skills Fit Score (0-100)
        skills_score = 0.0
        if comp_results and hasattr(comp_results, "skills_score"):
            skills_score = float(comp_results.skills_score or 0.0)
        else:
            skills_score = 50.0

        # 4. Experience Fit Score (0-100)
        experience_score = 0.0
        if comp_results and hasattr(comp_results, "experience_score"):
            experience_score = float(comp_results.experience_score or 0.0)
        else:
            cand_exp = context.candidate_experience or 0.0
            min_exp = job.min_experience or 0.0
            if cand_exp >= min_exp:
                experience_score = 100.0
            elif cand_exp >= (min_exp - 1.5):
                experience_score = 65.0
            else:
                experience_score = max(0.0, (cand_exp / min_exp) * 50.0 if min_exp > 0 else 0.0)

        # 5. Semantic Similarity Score (0-100)
        semantic_score = 0.0
        cand_text = f"Role: {context.current_role or ''}. Domain: {context.cand_tax_domain or ''}. Skills: {', '.join(context.cand_families)}. Summary: {cv_text[:300]}"
        vac_text = f"Title: {job.title}. Department: {job.department}. Description: {job.description[:300]}"

        cand_vector: list[float] | None = None
        vac_vector: list[float] | None = None
        try:
            from app.core.config import settings
            cand_vector = EmbeddingService.generate_embedding(cand_text, model_version=settings.EMBEDDING_MODEL, identifier=f"cand_fit_prof:{hash(cand_text)}")
            vac_vector = EmbeddingService.generate_embedding(vac_text, model_version=settings.EMBEDDING_MODEL, identifier=f"vac_fit_prof:{job.job_id}:{hash(vac_text)}")
        except Exception:
            pass

        if cand_vector and vac_vector:
            sim = max(0.0, min(1.0, float(EmbeddingService.cosine_similarity(cand_vector, vac_vector))))
            semantic_score = round(sim * 100.0, 1)
        else:
            semantic_score = float(getattr(comp_results, "responsibilities_score", 50.0) or 50.0)

        # Weighted combination
        w_hierarchy = 0.25
        w_role = 0.20
        w_skills = 0.25
        w_exp = 0.15
        w_semantic = 0.15

        raw_fit_score = (
            w_hierarchy * hierarchy_score +
            w_role * role_score +
            w_skills * skills_score +
            w_exp * experience_score +
            w_semantic * semantic_score
        )

        # Guardrail: High embedding similarity CANNOT override wrong department / invalid hierarchy
        if hierarchy_mismatch:
            final_fit_score = round(min(45.0, max(0.0, raw_fit_score - hierarchy_penalty)), 1)
            match_status = "NO_STRONG_VACANCY_MATCH"
            reason = f"Vacancy fit rejected ({final_fit_score:.1f}/100): Main Department or hierarchy mismatch."
        elif raw_fit_score < threshold:
            final_fit_score = round(raw_fit_score, 1)
            match_status = "NO_STRONG_VACANCY_MATCH"
            reason = f"Vacancy fit score ({final_fit_score:.1f}/100) below match threshold ({threshold:.1f})."
        else:
            final_fit_score = round(raw_fit_score, 1)
            match_status = "MATCHED"
            reason = f"Strong vacancy fit ({final_fit_score:.1f}/100): Valid hierarchy and skills alignment."

        breakdown = VacancyFitScoreBreakdown(
            hierarchy_score=round(hierarchy_score, 1),
            designation_role_score=round(role_score, 1),
            skills_score=round(skills_score, 1),
            experience_score=round(experience_score, 1),
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
    def classify_opening_fit(
        cls,
        opening: dict[str, Any] | Any,
        high_threshold: float = 70.0,
        potential_threshold: float = 50.0,
    ) -> str:
        """
        Canonical evaluator classification for an individual vacancy opening/match result.
        Returns one of: 'MATCHED', 'POTENTIAL_MATCH', or 'NO_STRONG_MATCH'.
        """
        if not opening:
            return VacancyMatchStatus.NO_STRONG_MATCH.value

        if isinstance(opening, dict):
            score = float(opening.get("vacancy_fit_score") or opening.get("score") or opening.get("overall_score") or 0.0)
            status = str(opening.get("vacancy_match_status") or opening.get("match_status") or "").upper()
            classification = str(opening.get("classification") or "").upper()
            failures = opening.get("mandatory_failures") or opening.get("mandatory_fails") or []
            has_domain_mismatch_req = any(
                isinstance(f, dict) and f.get("requirement_id") == "req_domain_mismatch"
                for f in failures
            )
            is_domain_rejected = bool(opening.get("domain_mismatch_capped") or opening.get("is_cross_domain") or has_domain_mismatch_req)
            score_breakdown = opening.get("score_breakdown")
            is_hierarchy_valid = True
            if isinstance(score_breakdown, dict):
                is_hierarchy_valid = score_breakdown.get("is_hierarchy_valid", True)
            elif hasattr(score_breakdown, "is_hierarchy_valid"):
                is_hierarchy_valid = getattr(score_breakdown, "is_hierarchy_valid", True)
        else:
            score = float(getattr(opening, "vacancy_fit_score", getattr(opening, "score", getattr(opening, "overall_score", 0.0))))
            status = str(getattr(opening, "vacancy_match_status", getattr(opening, "match_status", ""))).upper()
            classification = str(getattr(opening, "classification", "")).upper()
            failures = getattr(opening, "mandatory_failures", [])
            has_domain_mismatch_req = any(
                getattr(f, "requirement_id", None) == "req_domain_mismatch" for f in failures
            )
            is_domain_rejected = bool(getattr(opening, "domain_mismatch_capped", False) or getattr(opening, "is_cross_domain", False) or has_domain_mismatch_req)
            is_hierarchy_valid = getattr(getattr(opening, "score_breakdown", None), "is_hierarchy_valid", True)

        # Check hard rejection / hierarchy mismatch
        if is_domain_rejected or is_hierarchy_valid is False:
            return VacancyMatchStatus.NO_STRONG_MATCH.value

        is_high_class = classification in {"HIGH", "STRONG", "DB_MATCH", "HIGHLY_RECOMMENDED"} if classification else True

        if score >= high_threshold and is_high_class and status != "NO_STRONG_VACANCY_MATCH":
            return VacancyMatchStatus.MATCHED.value
        elif score >= potential_threshold:
            return VacancyMatchStatus.POTENTIAL_MATCH.value
        else:
            return VacancyMatchStatus.NO_STRONG_MATCH.value

    @classmethod
    def is_eligible_match(
        cls,
        opening: dict[str, Any] | Any,
        high_threshold: float = 70.0,
    ) -> bool:
        """Returns True if the opening is classified as a canonical MATCHED result."""
        return cls.classify_opening_fit(opening, high_threshold=high_threshold) == VacancyMatchStatus.MATCHED.value

    @classmethod
    def determine_candidate_match_status(
        cls,
        candidate_id: str,
        result_data: dict[str, Any] | None,
        vacancies_evaluated: list[dict[str, Any] | Any] | None,
        has_active_vacancies: bool = True,
        high_threshold: float = 70.0,
        potential_threshold: float = 50.0,
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

        proc_status = str(result_data.get("status") or "").lower()
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

