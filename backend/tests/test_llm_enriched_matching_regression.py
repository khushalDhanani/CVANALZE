from __future__ import annotations
import pytest
from unittest.mock import patch

from app.schemas.analysis import (
    OptimizedCandidateProfile,
    OptimizedLLMMatchResponse,
    OptimizedVacancyMatch,
)
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.classification_types import (
    HierarchyClassificationResult,
    HierarchyMatchNode,
)
from app.schemas.job_context import JobEvaluationContext
from app.schemas.match import JobMatchResult
from app.schemas.scoring_config import ScoringConfig
from app.services.match_service import MatchService
from app.services.scoring_engine import ScoringEngine


@pytest.fixture
def sample_candidate_context():
    cv_text = "Senior Flutter Developer with 5 years experience in Flutter, Dart, BLoC, and Software Engineering."
    ctx = CandidateAnalysisContext.create(
        cv_text=cv_text,
        candidate_experience=5.0,
    )
    ctx.current_role = "Senior Flutter Developer"
    ctx.cand_tax_domain = "Information Technology"
    ctx.cand_families = ["Flutter", "Dart", "Mobile App Development", "Software Engineering"]
    ctx.cand_hierarchy = HierarchyClassificationResult(
        main_department=HierarchyMatchNode(id=10, name="CIS Team", confidence=0.9, reasoning="Matched CIS Team", match_status="MATCHED"),
        department=HierarchyMatchNode(id=101, name="Software Engineering", confidence=0.88, reasoning="Matched Software Engineering", match_status="MATCHED"),
        designation=HierarchyMatchNode(id=1001, name="Senior Flutter Developer", confidence=0.92, reasoning="Matched Senior Flutter Developer", match_status="MATCHED"),
        is_hierarchy_valid=True,
        validation_errors=[],
        overall_confidence=0.9,
    )
    return ctx


@pytest.fixture
def sample_llm_match():
    return OptimizedVacancyMatch(
        vacancy_id=101,
        title="Senior Flutter Developer",
        department="Software Engineering",
        fit_level="HIGH",
        inferred_skills=["Flutter", "Dart", "BLoC", "REST API"],
        gap_analysis="Candidate satisfies all primary technical requirements.",
        career_transition_note="Direct domain alignment in mobile engineering.",
        semantic_reason="Candidate has 5+ years building production mobile apps in Flutter/Dart.",
    )


def test_1_llm_enriched_matching_no_nameerror(sample_candidate_context, sample_llm_match):
    """
    Regression Test 1: Verify evaluate_job_match executes cleanly with llm_match provided (LLM-enriched path).
    Ensures NameError: name 'kwargs' is not defined is completely eliminated.
    """
    raw_job = {
        "id": "JOB-101",
        "vacancy_id": 101,
        "title": "Senior Flutter Developer",
        "department": "Software Engineering",
        "description": "We are seeking a Senior Flutter Developer with 5+ years experience in Dart and Flutter.",
        "skills": ["Flutter", "Dart"],
        "min_experience_years": 5.0,
        "min_experience": 5.0,
        "main_department_id": 10,
        "department_id": 101,
        "designation_id": 1001,
    }
    job_ctx = JobEvaluationContext.create(raw_job)

    scoring_config = ScoringConfig.load()

    def mock_embed(text, *args, **kwargs):
        return [0.9, 0.1, 0.0]

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", side_effect=mock_embed):
        # 1. Test with llm_match (LLM-enriched path)
        res_llm = ScoringEngine.evaluate_job_match(
            cv_text=raw_job["description"],
            job=job_ctx,
            llm_match=sample_llm_match,
            scoring_config=scoring_config,
            context=sample_candidate_context,
            cand_hierarchy=sample_candidate_context.cand_hierarchy,
        )

        assert isinstance(res_llm, JobMatchResult)
        assert res_llm.job_id == "JOB-101"
        assert res_llm.vacancy_match_status == "MATCHED"
        assert res_llm.score_breakdown is not None
        assert res_llm.score_breakdown.hierarchy_score == 100.0

        # 2. Test without llm_match (Rule-based pre-filter path)
        res_rule = ScoringEngine.evaluate_job_match(
            cv_text=raw_job["description"],
            job=job_ctx,
            llm_match=None,
            scoring_config=scoring_config,
            context=sample_candidate_context,
            cand_hierarchy=sample_candidate_context.cand_hierarchy,
        )

        assert isinstance(res_rule, JobMatchResult)
        assert res_rule.job_id == "JOB-101"
        assert res_rule.vacancy_match_status == "MATCHED"


def test_2_multiple_vacancies_score_independently(sample_candidate_context):
    """
    Test 2: Multiple vacancies score independently in LLM-enriched matching.
    """
    jobs = [
        {
            "id": "JOB-101",
            "vacancy_id": 101,
            "title": "Senior Flutter Developer",
            "department": "Software Engineering",
            "description": "Flutter role with Dart and BLoC requirements.",
            "skills": ["Flutter", "Dart"],
            "min_experience_years": 5.0,
            "min_experience": 5.0,
            "main_department_id": 10,
            "department_id": 101,
            "designation_id": 1001,
        },
        {
            "id": "JOB-201",
            "vacancy_id": 201,
            "title": "Plant Operations Executive",
            "department": "Manufacturing",
            "description": "Manufacturing plant executive role in operations.",
            "skills": ["Operations", "Plant Safety"],
            "min_experience_years": 4.0,
            "min_experience": 4.0,
            "main_department_id": 20,
            "department_id": 201,
            "designation_id": 2001,
        },
    ]

    llm_matches = {
        "101": OptimizedVacancyMatch(
            vacancy_id=101,
            title="Senior Flutter Developer",
            department="Software Engineering",
            fit_level="HIGH",
            inferred_skills=["Flutter", "Dart"],
            gap_analysis="Strong fit",
            semantic_reason="Mobile app experience",
        ),
        "201": OptimizedVacancyMatch(
            vacancy_id=201,
            title="Plant Operations Executive",
            department="Manufacturing",
            fit_level="LOW",
            inferred_skills=[],
            gap_analysis="Domain mismatch",
            semantic_reason="Candidate is in software, not plant operations",
        ),
    }

    scoring_config = ScoringConfig.load()

    def mock_embed(text, *args, **kwargs):
        return [0.9, 0.1, 0.0]

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", side_effect=mock_embed):
        results = []
        for job_dict in jobs:
            job_ctx = JobEvaluationContext.create(job_dict)
            llm_match = llm_matches.get(str(job_dict["vacancy_id"]))
            res = ScoringEngine.evaluate_job_match(
                cv_text="5 years Flutter and Dart developer with mobile experience",
                job=job_ctx,
                llm_match=llm_match,
                scoring_config=scoring_config,
                context=sample_candidate_context,
                cand_hierarchy=sample_candidate_context.cand_hierarchy,
            )
            results.append(res)

        assert len(results) == 2
        # Job 101 is matched
        assert results[0].vacancy_id == 101
        assert results[0].vacancy_match_status == "MATCHED"
        assert results[0].score_breakdown.hierarchy_score == 100.0

        # Job 201 is rejected due to hierarchy mismatch
        assert results[1].vacancy_id == 201
        assert results[1].vacancy_match_status == "NO_STRONG_VACANCY_MATCH"
        assert results[1].score_breakdown.hierarchy_score == 0.0


@pytest.mark.asyncio
async def test_3_faulty_vacancy_does_not_destroy_other_matches():
    """
    Test 3: One faulty vacancy must not destroy candidate matching results for other valid vacancies.
    """
    cv_text = "Senior Flutter Developer with 5+ years experience in Dart, Mobile architecture, and REST APIs."

    vacancies = [
        {
            "id": 101,
            "vacancy_id": 101,
            "title": "Senior Flutter Developer",
            "department": "Software Engineering",
            "description": "Flutter role",
            "skills": ["Flutter", "Dart"],
            "experience_range": "4-8 years",
            "min_experience": 4.0,
            "main_department_id": 10,
            "department_id": 101,
            "designation_id": 1001,
        },
        {
            "id": 999,
            "vacancy_id": 999,
            "title": "Corrupted Vacancy",
            "department": "Corrupted Dept",
            "description": "Corrupted vacancy data",
            "skills": None,
            "experience_range": None,
            "min_experience": None,
        },
    ]

    mock_llm_response = OptimizedLLMMatchResponse(
        candidate_profile=OptimizedCandidateProfile(
            professional_domain="Information Technology",
            primary_department="Software Engineering",
            suitable_roles=["Senior Flutter Developer"],
            inferred_skills=["Flutter", "Dart"],
            relevant_experience_years=5.0,
        ),
        matched_vacancies=[
            OptimizedVacancyMatch(
                vacancy_id=101,
                title="Senior Flutter Developer",
                department="Software Engineering",
                fit_level="HIGH",
                inferred_skills=["Flutter", "Dart"],
                gap_analysis="Strong fit",
                semantic_reason="Direct Flutter match",
            )
        ],
    )

    with patch("app.services.llm_service.OllamaLLMService.run_optimized_match", return_value=mock_llm_response), \
         patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=[0.9, 0.1, 0.0]):

        analysis = await MatchService.analyze_single_cv(
            cv_text=cv_text,
            job_openings=vacancies,
            candidate_id="cand_test_001",
        )

        # Must have completed without crashing
        assert analysis is not None
        # Valid vacancy 101 should be processed
        assert len(analysis.suitable_openings) >= 1 or len(analysis.unsuitable_openings) >= 1
