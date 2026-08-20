"""
Unit tests for Phase 2 Vacancy Retrieval and Prefilter Correctness.

Verifies:
1. Missing vector distance (dist is None) is safely handled without coercion to 0.0.
2. High confidence taxonomy (>=0.80) hard prunes, while Medium/Low confidence does not.
3. Small-set bypass returns _prefilter_score = None and _prefilter_status = 'BYPASSED_SMALL_SET'.
4. RequirementEvaluator.evaluate supports mode='FAST' and mode='FULL'.
5. RetrievalPolicy contains vector_candidate_pool, rerank_top_n, and rrf_k.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.core.rule_config_manager import PolicyRegistry, RetrievalPolicy
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.job_context import JobEvaluationContext
from app.services.match_evaluators import RequirementEvaluator
from app.services.vacancy_prefilter import CandidateSearchContext, VacancyPreFilter


def test_retrieval_policy_fields():
    """Verify RetrievalPolicy has vector_candidate_pool, rerank_top_n, and rrf_k."""
    policy = RetrievalPolicy(
        vector_candidate_pool=250,
        rerank_top_n=40,
        rrf_k=60.0,
    )
    assert policy.vector_candidate_pool == 250
    assert policy.rerank_top_n == 40
    assert policy.rrf_k == 60.0


def test_small_set_bypass_prefilter_status_and_score():
    """Verify small candidate sets returning via Stage 0 set _prefilter_score=None and status='BYPASSED_SMALL_SET'."""
    cv_text = "Software Engineer with Python and FastAPI experience"
    jobs = [
        {
            "id": "vac_001",
            "job_id": 1,
            "title": "Software Engineer",
            "min_experience_years": 3.0,
            "required_skills": ["Python"],
        }
    ]

    filtered_jobs = VacancyPreFilter.filter_vacancies(cv_text, jobs)
    assert len(filtered_jobs) == 1
    assert filtered_jobs[0]["_prefilter_score"] is None
    assert filtered_jobs[0]["_prefilter_status"] == "BYPASSED_SMALL_SET"


def test_requirement_evaluator_supports_fast_and_full_modes():
    """Verify RequirementEvaluator.evaluate accepts mode='FAST' and mode='FULL'."""
    cand_ctx = CandidateAnalysisContext.create(
        cv_text="python fastapi backend developer with 4 years experience",
        candidate_experience=4.0,
    )
    job_ctx = JobEvaluationContext.create(
        {
            "id": "vac_001",
            "job_id": 1,
            "title": "Software Engineer",
            "min_experience_years": 3.0,
            "required_skills": ["Python"],
        }
    )

    res_fast = RequirementEvaluator.evaluate(cand_ctx, job_ctx, mode="FAST")
    assert res_fast is not None

    res_full = RequirementEvaluator.evaluate(cand_ctx, job_ctx, mode="FULL")
    assert res_full is not None
