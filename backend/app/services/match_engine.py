from typing import Any

from app.core.config import settings
from app.schemas.analysis import EnrichedJobMatchResult, QwenCVAnalysis
from app.services.scoring_engine import ScoringEngine


from app.schemas.profile import DynamicCandidateProfile

class MatchEngine:
    @classmethod
    def evaluate_job(
        cls, 
        cv_text: str, 
        job: dict[str, Any], 
        llm_analysis: QwenCVAnalysis | None,
        candidate_experience: float | None = None,
        candidate_ctc: float | None = None,
        dynamic_profile: DynamicCandidateProfile | None = None
    ) -> EnrichedJobMatchResult:
        # Get base keyword-based result
        base_match = ScoringEngine.evaluate_job_match(
            cv_text, 
            job, 
            candidate_experience=candidate_experience,
            candidate_ctc=candidate_ctc,
            dynamic_profile=dynamic_profile
        )

        req_skills = job.get("required_skills", [])
        pref_keywords = job.get("preferred_keywords", [])

        # Default scores if LLM failed or disabled
        skill_score = (
            (len(base_match.matched_skills) / len(req_skills) * 100.0)
            if req_skills
            else 100.0
        )
        keyword_score = (
            (len(base_match.matched_keywords) / len(pref_keywords) * 100.0)
            if pref_keywords
            else 100.0
        )

        llm_reason = ""
        inferred_skills = []
        llm_boost = 0.0

        if llm_analysis:
            llm_reason = llm_analysis.semantic_reason
            inferred_skills = [
                s
                for s in llm_analysis.inferred_skills
                if s.lower() not in [m.lower() for m in base_match.matched_skills]
            ]

            # Boost score based on inferred skills
            raw_boost = len(inferred_skills) * (settings.LLM_BOOST_WEIGHT * 100)
            llm_boost = min(raw_boost, settings.MAX_LLM_BOOST)

            # We can also add inferred skills into matched_skills logically,
            # but we keep them separate in EnrichedJobMatchResult for clarity.

        raw_score = (
            (skill_score * settings.SKILL_WEIGHT)
            + (keyword_score * settings.KEYWORD_WEIGHT)
            + llm_boost
        )
        final_score = round(min(100.0, max(0.0, raw_score)), 1)

        if final_score >= settings.MATCH_HIGH_THRESHOLD:
            classification = "HIGH"
            recommendation = "Strong match — Fast-track to interview."
        elif final_score >= settings.MATCH_MEDIUM_THRESHOLD:
            classification = "MEDIUM"
            recommendation = "Potential match — HR review recommended."
        else:
            classification = "LOW"
            recommendation = "Significant requirements missing — Manual HR review required (never auto-rejected)."

        return EnrichedJobMatchResult(
            job_id=base_match.job_id,
            job_title=base_match.job_title,
            department=base_match.department,
            vacancy_id=base_match.vacancy_id,
            job_profile_id=base_match.job_profile_id,
            company_id=base_match.company_id,
            department_id=base_match.department_id,
            department_name=base_match.department_name,
            location_id=base_match.location_id,
            score=base_match.score,
            overall_score=base_match.overall_score,
            classification=base_match.classification,
            recommendation=base_match.recommendation,
            matched_skills=base_match.matched_skills,
            missing_skills=base_match.missing_skills,
            matched_keywords=base_match.matched_keywords,
            missing_keywords=base_match.missing_keywords,
            mandatory_requirements=base_match.mandatory_requirements,
            preferred_requirements=base_match.preferred_requirements,
            optional_requirements=base_match.optional_requirements,
            matched_criteria=base_match.matched_criteria,
            missing_criteria=base_match.missing_criteria,
            evidence=base_match.evidence,
            mandatory_failures=base_match.mandatory_failures,
            confidence=base_match.confidence,
            hr_review_required=base_match.hr_review_required,
            reason=base_match.reason or llm_reason,
            career_transition_detected=base_match.career_transition_detected,
            career_transition_note=base_match.career_transition_note,
            llm_reason=llm_reason,
            inferred_skills=inferred_skills,
        )

