from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.core.profiler import PipelineProfiler
from app.prompts.optimized_match import build_optimized_match_prompt
from app.repositories.llm_cache import LLMCacheRepository
from app.schemas.analysis import (
    OptimizedCandidateProfile,
    OptimizedLLMMatchResponse,
    OptimizedVacancyMatch,
)
from app.services.llm_service import OllamaLLMService
from app.services.match_service import MatchService
from app.services.vacancy_prefilter import VacancyPreFilter


def test_vacancy_prefilter():
    cv_text = """
    Senior Python Developer with 6 years experience in FastAPI, Docker, PostgreSQL, and AWS.
    Built scalable microservices and RESTful APIs.
    """
    vacancies = [
        {
            "id": 1,
            "vacancy_id": 1,
            "title": "Python Developer",
            "department": "Engineering",
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "preferred_keywords": ["Docker", "AWS"],
            "min_experience_years": 4,
        },
        {
            "id": 2,
            "vacancy_id": 2,
            "title": "Java Developer",
            "department": "Engineering",
            "required_skills": ["Java", "Spring Boot"],
            "preferred_keywords": ["Microservices"],
            "min_experience_years": 3,
        },
        {
            "id": 3,
            "vacancy_id": 3,
            "title": "UI/UX Designer",
            "department": "Design",
            "required_skills": ["Figma", "Adobe XD"],
            "preferred_keywords": ["Wireframing"],
            "min_experience_years": 2,
        },
    ]

    filtered = VacancyPreFilter.filter_vacancies(
        cv_text=cv_text, openings=vacancies, top_k=2
    )

    assert len(filtered) == 2
    top_titles = [j["title"] for j in filtered]
    assert "Python Developer" in top_titles
    assert "UI/UX Designer" not in top_titles


def test_pipeline_profiler():
    profiler = PipelineProfiler()
    with profiler.time_stage("prefilter"):
        _ = sum(range(1000))

    with profiler.time_stage("prompt_construction"):
        _ = "a" * 500

    metrics = profiler.finish()
    assert metrics.prefilter_ms >= 0.0
    assert metrics.prompt_construction_ms >= 0.0
    assert metrics.total_execution_ms >= 0.0


def test_composite_cache_hash_and_repository(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path)


    key1 = LLMCacheRepository.compute_composite_hash(
        document_hash="abc123",
        candidate_id="42",
        vacancy_ids=["101"],
        prompt_version="3.0",
        model_version="qwen3:4b",
        matching_version="3.0",
    )
    key2 = LLMCacheRepository.compute_composite_hash(
        document_hash="abc123",
        candidate_id="42",
        vacancy_ids=["101"],
        prompt_version="3.0",
        model_version="qwen3:4b",
        matching_version="3.0",
    )
    assert key1 == key2

    # Changing any component produces a different key
    key3 = LLMCacheRepository.compute_composite_hash(
        document_hash="abc123",
        candidate_id="42",
        vacancy_ids=["101"],
        prompt_version="3.0",
        model_version="qwen3:4b",
        matching_version="3.1",
    )
    assert key1 != key3

    sample_response = OptimizedLLMMatchResponse(
        candidate_profile=OptimizedCandidateProfile(
            core_skills=["Python", "FastAPI"],
            relevant_experience_years=5.0,
            current_role="Python Engineer",
        ),
        matched_vacancies=[
            OptimizedVacancyMatch(
                vacancy_id=101,
                semantic_reason="Strong fit for Python Dev",
                semantic_fit_score=90.0,
            )
        ],
    )

    LLMCacheRepository.save_cached_object(key1, sample_response)

    cached = LLMCacheRepository.get_cached_object(key1, OptimizedLLMMatchResponse)
    assert cached is not None
    assert cached.candidate_profile.relevant_experience_years == 5.0
    assert cached.matched_vacancies[0].vacancy_id == 101


def test_build_optimized_match_prompt():
    cv_text = """
    John Doe
    Software Engineer
    Skills: Python, FastAPI, Docker
    """
    vacancies = [
        {
            "vacancy_id": 1,
            "title": "Backend Engineer",
            "department": "Engineering",
            "required_skills": ["Python", "FastAPI"],
        }
    ]

    prompt, token_est, char_count = build_optimized_match_prompt(cv_text, vacancies)
    assert "John Doe" in prompt
    assert "Backend Engineer" in prompt
    assert token_est > 0
    assert char_count > 0


@pytest.mark.asyncio
async def test_end_to_end_optimized_match_service(monkeypatch):
    from app.core.cache import match_result_cache_manager
    match_result_cache_manager.clear()
    monkeypatch.setattr(settings, "LLM_SKIP_COVERAGE_THRESHOLD", 1.1)

    cv_text = """
    ## HITESH GHOGHARI
    Senior Frontend Developer
    Skills: HTML5, CSS3, JavaScript, React, Tailwind CSS, Git
    Experience: 8 years building web applications and React components.
    """

    mock_llm_response = OptimizedLLMMatchResponse(
        candidate_profile=OptimizedCandidateProfile(
            core_skills=["HTML5", "CSS3", "JavaScript", "React"],
            inferred_skills=["Web Development"],
            relevant_experience_years=8.0,
            current_role="Senior Frontend Developer",
        ),
        matched_vacancies=[
            OptimizedVacancyMatch(
                vacancy_id=101,
                semantic_reason="Strong React experience matches Frontend requirement.",
                semantic_fit_score=85.0,
            )
        ],
    )

    monkeypatch.setattr(
        OllamaLLMService, "run_optimized_match", MagicMock(return_value=mock_llm_response)
    )

    openings = [
        {
            "id": 101,
            "vacancy_id": 101,
            "title": "Frontend Developer",
            "department": "Engineering",
            "required_skills": ["React", "JavaScript", "HTML5"],
            "preferred_keywords": ["Tailwind CSS"],
            "min_experience_years": 5,
        }
    ]

    analysis = await MatchService.analyze_single_cv(cv_text, job_openings=openings)

    assert analysis.primary_department is not None
    assert len(analysis.suitable_openings) == 1
    best = analysis.best_match
    assert best.score >= 70.0
    assert best.classification == "HIGH"
    assert "React" in best.matched_skills

