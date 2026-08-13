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

    filtered = VacancyPreFilter.filter_vacancies(cv_text=cv_text, openings=vacancies, top_k=2)

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
        model_version="llama3.2:3b",
        matching_version="3.0",
    )
    key2 = LLMCacheRepository.compute_composite_hash(
        document_hash="abc123",
        candidate_id="42",
        vacancy_ids=["101"],
        prompt_version="3.0",
        model_version="llama3.2:3b",
        matching_version="3.0",
    )
    assert key1 == key2

    # Changing any component produces a different key
    key3 = LLMCacheRepository.compute_composite_hash(
        document_hash="abc123",
        candidate_id="42",
        vacancy_ids=["101"],
        prompt_version="3.0",
        model_version="llama3.2:3b",
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
                top_strength="The CV documents production Python work that directly matches the vacancy's Python requirement. This is the clearest role-specific strength in the supplied evidence.",
                main_concern="The CV does not state the deployment scale expected by the vacancy. Recruiters should verify production ownership and traffic volume rather than infer them.",
                ai_match_explanation="The high score reflects the explicit Python overlap between the CV and vacancy. The score remains limited by the missing deployment-scale evidence.",
                semantic_fit_score=90.0,
            )
        ],
        active_vacancy_summary="Python vacancy evaluated.",
        ai_career_summary="Backend engineering profile.",
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
            "required_skills_are_mandatory": False,
            "education": "Configured Degree",
            "technologies": ["Docker"],
            "responsibilities": ["Build APIs"],
            "description": "Own backend services",
            "max_experience_years": 8,
            "max_ctc": 25,
        }
    ]

    from unittest.mock import patch
    with patch("app.services.prompt_service.PromptService.get_prompt") as mock_get_prompt:
        mock_get_prompt.return_value = "John Doe Backend Engineer"
        prompt, token_est, char_count = build_optimized_match_prompt(cv_text, vacancies)
    prompt_input = mock_get_prompt.call_args.args[1]["input_json"]
    assert '"education_req":["Configured Degree"]' in prompt_input
    assert '"required_skills_are_mandatory":false' in prompt_input
    assert '"technologies":["Docker"]' in prompt_input
    assert '"responsibilities":["Build APIs"]' in prompt_input
    assert '"description":"Own backend services"' in prompt_input
    assert '"max_exp":8' in prompt_input
    assert '"max_ctc":25' in prompt_input
    assert "John Doe" in prompt
    assert "Backend Engineer" in prompt
    assert token_est > 0
    assert char_count > 0


def test_optimized_response_rejects_shallow_payloads():
    with pytest.raises(ValueError):
        OptimizedLLMMatchResponse.model_validate({})

    with pytest.raises(ValueError):
        OptimizedLLMMatchResponse.model_validate(
            {
                "candidate_profile": {},
                "matched_vacancies": [{"vacancy_id": 1}],
            }
        )


def test_optimized_vacancy_match_rejects_single_sentence_decision_narratives():
    single_sentence = "The CV lists Python and the vacancy requires Python, but this single sentence is not detailed enough for a recruiter."

    with pytest.raises(ValueError, match="two or three complete sentences"):
        OptimizedVacancyMatch(
            vacancy_id=101,
            semantic_reason="Python overlap.",
            top_strength=single_sentence,
            main_concern="The CV does not state deployment scale. Recruiters should verify production ownership.",
            ai_match_explanation="The score reflects the Python match. Missing deployment evidence limits confidence.",
            semantic_fit_score=80.0,
        )


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
                top_strength="The CV explicitly lists React experience, matching the vacancy's frontend framework requirement. This is the strongest documented role-specific overlap.",
                main_concern="The CV does not quantify production ownership for the React work required by the vacancy. Recruiters should verify project scale and individual contribution.",
                ai_match_explanation="The score is driven by the direct React match between the CV and vacancy. It is constrained by the absence of quantified delivery evidence in the CV.",
                semantic_fit_score=85.0,
            )
        ],
        active_vacancy_summary="Frontend vacancy evaluated.",
        ai_career_summary="Frontend engineering profile.",
    )

    monkeypatch.setattr(
        OllamaLLMService,
        "run_optimized_match",
        MagicMock(return_value=mock_llm_response),
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
