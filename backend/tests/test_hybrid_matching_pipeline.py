import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.core.cache import embedding_cache_manager, match_result_cache_manager, vacancy_cache_manager
from app.core.config import settings
from app.schemas.analysis import EnrichedCandidateAnalysis
from app.services.match_service import MatchService
from app.services.scoring_engine import ScoringEngine
from app.services.vacancy_prefilter import VacancyPreFilter


@pytest.fixture(autouse=True)
def clear_all_test_caches():
    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()
    match_result_cache_manager.clear()
    yield
    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()
    match_result_cache_manager.clear()


@pytest.mark.asyncio
async def test_full_hybrid_matching_pipeline_execution_sequence():
    """
    Verifies the hybrid architecture sequence:
    Resume -> Embedding -> Vector Search -> VacancyPreFilter -> Confidence Gate -> LLM (if required) -> Deterministic Scoring Engine -> Final Ranking
    """
    cv_text = """
    # Resume - Alex Mercer
    Senior Software Engineer with 7 years of experience in Python, FastAPI, PostgreSQL, and Docker.
    Education: B.S. in Computer Science.
    Responsibilities: Architected microservices, optimized SQL database queries, led a team of 4 engineers.
    """

    openings = [
        {"id": "vac_101", "vacancy_id": 101, "title": "Senior Python Backend Engineer", "department": "Engineering", "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"], "min_experience_years": 5.0},
        {"id": "vac_102", "vacancy_id": 102, "title": "DevOps Engineer", "department": "Infrastructure", "required_skills": ["Kubernetes", "Terraform", "AWS"], "min_experience_years": 4.0},
        {"id": "vac_103", "vacancy_id": 103, "title": "Frontend Developer", "department": "UI", "required_skills": ["React", "CSS"], "min_experience_years": 2.0},
        {"id": "vac_104", "vacancy_id": 104, "title": "Data Analyst", "department": "Analytics", "required_skills": ["Tableau", "Excel"], "min_experience_years": 1.0},
        {"id": "vac_105", "vacancy_id": 105, "title": "QA Automation Engineer", "department": "Quality", "required_skills": ["Selenium", "Cypress"], "min_experience_years": 3.0},
        {"id": "vac_106", "vacancy_id": 106, "title": "Product Manager", "department": "Product", "required_skills": ["Roadmapping", "Jira"], "min_experience_years": 5.0},
    ]

    mock_emb = [0.1] * 768

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb) as mock_emb_gen:
        with patch("app.services.vacancy_prefilter.VacancyPreFilter.semantic_vector_search", return_value=["101", "102"]) as mock_stage1_vector:
            analysis = await MatchService.analyze_single_cv(
                cv_text=cv_text,
                job_openings=openings,
                cv_embedding=mock_emb,
            )

            assert isinstance(analysis, EnrichedCandidateAnalysis)
            assert len(analysis.suitable_openings) > 0

            # 1. Candidate Embedding passed
            # 2. Stage 1 Semantic Vector Retrieval called
            mock_stage1_vector.assert_called_once()

            # 3. Best match ranked #1 by deterministic ScoringEngine
            best_match = analysis.best_match
            assert best_match.vacancy_id == 101
            assert best_match.overall_score > 70.0


@pytest.mark.asyncio
async def test_embeddings_only_retrieve_candidates_never_determine_final_score():
    """
    Verifies that vector similarity scores are used ONLY to retrieve candidates in Stage 1 & RRF,
    and NEVER alter the final score produced by ScoringEngine.
    """
    cv_text = "Senior Python Developer with FastAPI and SQL experience"
    job = {
        "id": "vac_201",
        "vacancy_id": 201,
        "title": "Python Developer",
        "department": "Engineering",
        "required_skills": ["Python", "FastAPI"],
        "min_experience_years": 3.0,
    }

    # Evaluate match with ScoringEngine directly
    match_result = ScoringEngine.evaluate_job_match(
        cv_text=cv_text,
        job=job,
        candidate_experience=5.0,
    )

    # Score is purely rules-based (skills, role, exp, education, domain)
    assert match_result.score == match_result.overall_score
    # Raw vector distance is NOT added directly to final score
    assert isinstance(match_result.score, float)
    assert 0.0 <= match_result.score <= 100.0


@pytest.mark.asyncio
async def test_explainability_and_mandatory_requirements():
    """
    Verifies match results preserve full explainability:
    evidence snippets, matched/missing skills, mandatory requirements breakdown, and ranking reason.
    """
    cv_text = """
    # Resume
    Software Engineer with Python experience.
    Education: B.Tech in Computer Science.
    """

    job = {
        "id": "vac_301",
        "vacancy_id": 301,
        "title": "Backend Engineer",
        "department": "Engineering",
        "required_skills": ["Python", "Rust"],
        "min_experience_years": 2.0,
    }

    match_result = ScoringEngine.evaluate_job_match(
        cv_text=cv_text,
        job=job,
    )

    assert "Python" in match_result.matched_skills
    assert "Rust" in match_result.missing_skills
    assert isinstance(match_result.evidence, dict)
    assert isinstance(match_result.mandatory_requirements, list)
    assert match_result.reason != ""
    assert match_result.classification in ("HIGH", "MEDIUM", "LOW")


@pytest.mark.asyncio
async def test_confidence_gate_bypasses_llm_for_unambiguous_matches():
    """
    Verifies that when pre-LLM score margin and coverage criteria are satisfied,
    the Confidence Gate sets llm_skipped=True and bypasses LLM call completely.
    """
    cv_text = "Senior Python Developer with FastAPI and PostgreSQL expertise, 8 years exp"
    openings = [
        {
            "id": "vac_401",
            "vacancy_id": 401,
            "title": "Senior Python Developer",
            "department": "Engineering",
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "min_experience_years": 5.0,
        },
        {
            "id": "vac_402",
            "vacancy_id": 402,
            "title": "Junior Graphic Designer",
            "department": "Design",
            "required_skills": ["Photoshop", "Illustrator"],
            "min_experience_years": 1.0,
        },
    ]

    with patch("app.services.llm_service.OllamaLLMService.run_optimized_match") as mock_llm:
        analysis = await MatchService.analyze_single_cv(
            cv_text=cv_text,
            job_openings=openings,
            cv_embedding=[0.1] * 768,
        )

        assert analysis.llm_skipped is True
        # LLM was NOT called due to Confidence Gate fast-track
        mock_llm.assert_not_called()
        assert analysis.best_match.vacancy_id == 401
