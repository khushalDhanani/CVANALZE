from __future__ import annotations
import functools
import re
from typing import Any

from app.core.rule_config_manager import RuleConfigManager
from app.repositories.department_domain import (
    DepartmentDomainRepository,
    department_domain_repository,
)
from app.repositories.job import JobRepository
from app.schemas.analysis import OptimizedCandidateProfile, OptimizedVacancyMatch
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.job_context import JobEvaluationContext
from app.schemas.match import (
    CandidateMatchAnalysis,
    JobMatchResult,
)
from app.schemas.profile import DynamicCandidateProfile
from app.schemas.scoring_config import ScoringConfig
from app.services.candidate_domain_service import CandidateDomainService
from app.services.match_evaluators import (
    CareerTransitionEvaluator,
    ComponentScoreEvaluator,
    CrossDomainGuardEvaluator,
    RecommendationEvaluator,
    RequirementEvaluator,
    is_ignorable_requirement,
)


class ScoringEngine:
    # Repository instance is swappable in tests via dependency injection.
    domain_repository: DepartmentDomainRepository = department_domain_repository

    @classmethod
    def extract_candidate_domain_profile(
        cls,
        cv_text: str,
        dynamic_profile: DynamicCandidateProfile | None = None,
        optimized_profile: OptimizedCandidateProfile | None = None,
        resume_json: dict[str, Any] | None = None,
        domain_repository: DepartmentDomainRepository | None = None,
    ) -> dict[str, Any]:
        """Identifies candidate's most suitable department and professional domain."""
        return CandidateDomainService.extract_candidate_domain_profile(
            cv_text=cv_text,
            dynamic_profile=dynamic_profile,
            optimized_profile=optimized_profile,
            resume_json=resume_json,
            domain_repository=domain_repository or cls.domain_repository,
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        return text.lower()

    @classmethod
    def _extract_cv_skill_lines(cls, cv_text: str) -> list[str]:
        skill_lines: list[str] = []
        in_skills_section = False

        for raw_line in cv_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            normalized_heading = re.sub(r"\s+", " ", line.lstrip("#- ").strip()).lower()
            compact_heading = normalized_heading.replace(" ", "")

            if compact_heading == "skills":
                in_skills_section = True
                continue

            if in_skills_section and line.startswith("##"):
                break

            if in_skills_section or re.match(r"^[\w /&+\-.#]+:\s*\S+", line):
                skill_lines.append(line)

        return skill_lines

    @classmethod
    def _extract_cv_role_headers(cls, cv_text: str) -> list[str]:
        headers: list[str] = []
        match_rules = RuleConfigManager.get_match_rules()
        section_denylist = {h.lower().strip() for h in match_rules.cv_section_heading_denylist if h}
        compact_denylist = {h.lower().strip() for h in match_rules.cv_section_heading_compact_denylist if h}
        substring_denylist = [h.lower().strip() for h in match_rules.cv_section_heading_substring_denylist if h]

        for raw_line in cv_text.splitlines():
            line = raw_line.strip()
            if not line.startswith("##"):
                continue

            header = re.sub(r"\s+", " ", line.lstrip("# ").strip())
            normalized_header = header.lower()
            compact_header = re.sub(r"\s+", "", normalized_header)
            if not header or normalized_header in section_denylist or compact_header in compact_denylist or any(term in normalized_header for term in substring_denylist):
                continue
            headers.append(header)

        return headers

    @classmethod
    def _build_domain_candidate_text(
        cls,
        cv_text: str,
        current_role: str | None = None,
        dynamic_profile: DynamicCandidateProfile | None = None,
        optimized_profile: OptimizedCandidateProfile | None = None,
        llm_match: OptimizedVacancyMatch | None = None,
        domain_repository: DepartmentDomainRepository | None = None,
    ) -> str:
        return CandidateDomainService.build_domain_candidate_text(
            cv_text=cv_text,
            current_role=current_role,
            dynamic_profile=dynamic_profile,
            optimized_profile=optimized_profile,
            llm_match=llm_match,
            domain_repository=domain_repository or cls.domain_repository,
        )

    @classmethod
    def _extract_department_domain_terms(cls, department: str) -> list[str]:
        return CandidateDomainService.extract_department_domain_terms(department)

    @staticmethod
    @functools.lru_cache(maxsize=2048)
    def _get_compiled_term_pattern(term_lower: str) -> re.Pattern[str]:
        escaped = re.escape(term_lower)
        if re.search(r"[\+\#\.]", term_lower):
            pattern = r"(?:^|[\s,;/()\-_\"\'])" + escaped + r"(?:$|[\s,;/()\-_\"\'])"
        else:
            pattern = r"(?:\b|_)" + escaped + r"(?:\b|_)"
        return re.compile(pattern, re.IGNORECASE)

    @classmethod
    def _extract_term_matches(cls, normalized_text: str, terms: list[str]) -> tuple[list[str], list[str]]:
        matched = []
        missing = []

        assets = RuleConfigManager.get_term_matching_assets()
        noise_words = set(assets.get("noise_words", []))
        noise_words.update(["general", "knowledge", "basic", "advanced", "good", "excellent", "working", "understanding", "hands-on", "familiarity", "experience", "skills", "ability"])
        noise_words = list(noise_words)
        aliases = assets["aliases"]

        for term in terms:
            term_clean = term.strip()
            if not term_clean or is_ignorable_requirement(term):
                continue

            term_lower = term_clean.lower()

            pattern = cls._get_compiled_term_pattern(term_lower)
            if pattern.search(normalized_text):
                matched.append(term)
                continue

            # Check Aliases
            if term_lower in aliases:
                alt_matched = False
                for alt in aliases[term_lower]:
                    alt_pattern = cls._get_compiled_term_pattern(alt)
                    if alt_pattern.search(normalized_text):
                        matched.append(term)
                        alt_matched = True
                        break
                if alt_matched:
                    continue

            # Sub-token matching (stripping noise/filler words) is only used for
            # SHORT skills (<= 3 meaningful tokens) and requires EVERY token to
            # appear in the CV text. A single shared token must not fabricate a
            # match for a longer phrase (e.g. "HPLC knowledge" is NOT proven by
            # the word "knowledge" alone; "Plant Commission" requires both
            # "plant" AND "commission").
            sub_tokens = [w for w in re.split(r"[\s,;/()\-_]+", term_lower) if w and w not in noise_words and len(w) > 1]
            if 1 <= len(sub_tokens) <= 3 and all(
                cls._get_compiled_term_pattern(tok).search(normalized_text) for tok in sub_tokens
            ):
                matched.append(term)
                continue

            missing.append(term)

        return matched, missing

    @classmethod
    def evaluate_job_match(
        cls,
        cv_text: str,
        job: dict[str, Any] | JobEvaluationContext,
        candidate_experience: float | None = None,
        candidate_ctc: float | None = None,
        dynamic_profile: DynamicCandidateProfile | None = None,
        optimized_profile: OptimizedCandidateProfile | None = None,
        llm_match: OptimizedVacancyMatch | None = None,
        scoring_config: dict[str, float] | ScoringConfig | None = None,
        context: CandidateAnalysisContext | None = None,
    ) -> JobMatchResult:
        if context is None:
            context = CandidateAnalysisContext.create(
                cv_text=cv_text,
                candidate_experience=candidate_experience,
                candidate_ctc=candidate_ctc,
                dynamic_profile=dynamic_profile,
                optimized_profile=optimized_profile,
                domain_repository=cls.domain_repository,
            )

        job_ctx = job if isinstance(job, JobEvaluationContext) else JobEvaluationContext.create(job)
        typed_scoring_config = scoring_config if isinstance(scoring_config, ScoringConfig) else ScoringConfig.load(scoring_config)

        # 1. Requirement Evaluations
        req_results = RequirementEvaluator.evaluate(
            context=context,
            job=job_ctx,
            llm_match=llm_match,
            scoring_config=typed_scoring_config,
            extract_term_matches_fn=cls._extract_term_matches,
        )

        # 2. Career Transition Detection
        transition_detected, transition_note, common_words = CareerTransitionEvaluator.evaluate(
            context=context,
            job=job_ctx,
            llm_match=llm_match,
        )

        # 3. Component Score Calculations & Weighted Raw Score
        comp_results = ComponentScoreEvaluator.evaluate(
            context=context,
            job=job_ctx,
            req_results=req_results,
            transition_detected=transition_detected,
            common_words=common_words,
            llm_match=llm_match,
            scoring_config=typed_scoring_config,
            extract_term_matches_fn=cls._extract_term_matches,
        )

        # 4. Cross-Domain Divergence Guard
        guard_results = CrossDomainGuardEvaluator.evaluate(
            context=context,
            job=job_ctx,
            initial_score=comp_results.final_score,
            initial_domain_score=comp_results.domain_score,
            reason_str=comp_results.reason_str,
            mandatory_failures=req_results.mandatory_failures,
        )

        if guard_results.additional_mandatory_failures:
            req_results.mandatory_failures.extend(guard_results.additional_mandatory_failures)

        # 5. Recommendation & Confidence
        total_req_count = len(req_results.mandatory_reqs) + len(req_results.preferred_reqs) + len(req_results.optional_reqs)
        evidence_count = len(req_results.evidence_map)

        rec_results = RecommendationEvaluator.evaluate(
            final_score=guard_results.final_score,
            component_coverage=comp_results.component_coverage,
            total_req_count=total_req_count,
            evidence_count=evidence_count,
            scoring_config=typed_scoring_config,
            reason_str=guard_results.reason_str,
            missing_criteria=req_results.missing_criteria,
        )

        def safe_round(val: float | None) -> float:
            return round(val, 1) if val is not None else 0.0

        raw_job = job_ctx.raw_job

        # Retrieval source details
        retrieval_src = str(raw_job.get("_retrieval_source") or "keyword")
        rrf_details = raw_job.get("_rrf_details", {})
        if isinstance(rrf_details, dict):
            has_lexical = rrf_details.get("lexical_rank") is not None
            has_vector = rrf_details.get("vector_rank") is not None
            if has_lexical and has_vector:
                retrieval_src = "both"
            elif has_vector:
                retrieval_src = "vector"
            elif has_lexical:
                retrieval_src = "keyword"

        return JobMatchResult(
            job_id=job_ctx.job_id,
            job_title=job_ctx.title,
            department=job_ctx.department,
            vacancy_id=raw_job.get("vacancy_id"),
            job_profile_id=raw_job.get("job_profile_id"),
            company_id=raw_job.get("company_id"),
            department_id=raw_job.get("department_id"),
            department_name=raw_job.get("department_name") or raw_job.get("department"),
            location_id=raw_job.get("location_id"),
            score=guard_results.final_score,
            overall_score=guard_results.final_score,
            classification=rec_results.classification,
            recommendation=rec_results.recommendation,
            role_score=safe_round(comp_results.role_score),
            skills_score=safe_round(comp_results.skills_score),
            experience_score=safe_round(comp_results.experience_score),
            education_score=safe_round(comp_results.education_score),
            domain_score=safe_round(guard_results.domain_score),
            technology_score=safe_round(comp_results.technology_score),
            certification_score=safe_round(comp_results.certification_score),
            responsibilities_score=safe_round(comp_results.responsibilities_score),
            coverage=round(comp_results.coverage, 2),
            matched_skills=req_results.matched_skills,
            missing_skills=req_results.missing_skills,
            matched_keywords=req_results.matched_keywords,
            missing_keywords=req_results.missing_keywords,
            mandatory_requirements=req_results.mandatory_reqs,
            preferred_requirements=req_results.preferred_reqs,
            optional_requirements=req_results.optional_reqs,
            matched_criteria=req_results.matched_criteria,
            missing_criteria=req_results.missing_criteria,
            evidence=req_results.evidence_map,
            mandatory_failures=req_results.mandatory_failures,
            mandatory_fails=[
                {
                    "requirement": f.description,
                    "details": f.reason,
                    "impact": f.score_impact,
                }
                for f in req_results.mandatory_failures
            ],
            confidence=rec_results.confidence_val,
            hr_review_required=comp_results.hr_review_required,
            domain_mismatch_capped=guard_results.is_domain_capped,
            domain_mismatch_reason=guard_results.domain_capped_reason,
            reason=rec_results.reason_str,
            career_transition_detected=transition_detected,
            career_transition_note=transition_note,
            retrieval_source=retrieval_src,
        )

    @classmethod
    def analyze_cv(
        cls,
        cv_text: str,
        dynamic_profile: DynamicCandidateProfile | None = None,
        job_openings: list[dict[str, Any]] | list[JobEvaluationContext] | None = None,
        profiler: Any | None = None,
    ) -> CandidateMatchAnalysis:
        openings = job_openings if job_openings is not None else JobRepository.get_all_jobs()
        scoring_config = ScoringConfig.load()

        if profiler:
            with profiler.time_stage("vacancy_context"):
                job_contexts = [j if isinstance(j, JobEvaluationContext) else JobEvaluationContext.create(j) for j in openings]
            with profiler.time_stage("candidate_context"):
                context = CandidateAnalysisContext.create(
                    cv_text,
                    dynamic_profile=dynamic_profile,
                    domain_repository=cls.domain_repository,
                )
            with profiler.time_stage("scoring"):
                evaluated_matches = [
                    cls.evaluate_job_match(
                        cv_text,
                        job_ctx,
                        dynamic_profile=dynamic_profile,
                        context=context,
                        scoring_config=scoring_config,
                    )
                    for job_ctx in job_contexts
                ]
        else:
            job_contexts = [j if isinstance(j, JobEvaluationContext) else JobEvaluationContext.create(j) for j in openings]
            context = CandidateAnalysisContext.create(
                cv_text,
                dynamic_profile=dynamic_profile,
                domain_repository=cls.domain_repository,
            )
            evaluated_matches = [
                cls.evaluate_job_match(
                    cv_text,
                    job_ctx,
                    dynamic_profile=dynamic_profile,
                    context=context,
                    scoring_config=scoring_config,
                )
                for job_ctx in job_contexts
            ]

        evaluated_matches.sort(key=lambda m: m.score, reverse=True)

        high_threshold = scoring_config.match_high_threshold
        suitable_matches = [
            m
            for m in evaluated_matches
            if m.score >= high_threshold and m.classification == "HIGH" and not m.domain_mismatch_capped
        ]
        unsuitable_matches = [m for m in evaluated_matches if m not in suitable_matches]
        best_match = suitable_matches[0] if suitable_matches else None

        return CandidateMatchAnalysis(
            primary_department=best_match.department if best_match else "",
            best_match=best_match,
            suitable_openings=suitable_matches,
            unsuitable_openings=unsuitable_matches,
        )
