from unittest.mock import patch

import pytest

from app.core.cache import embedding_cache_manager, vacancy_cache_manager
from app.core.config import settings
from app.services.scoring_engine import ScoringEngine
from app.services.vacancy_prefilter import VacancyPreFilter


@pytest.fixture(autouse=True)
def clear_caches():
    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()
    yield
    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()


def test_stage1_semantic_retrieval_narrows_openings():
    openings = [
        {"id": "vac_1", "vacancy_id": 1, "title": "Senior Python Backend Developer", "department": "Engineering", "required_skills": ["Python"]},
        {"id": "vac_2", "vacancy_id": 2, "title": "React Frontend Developer", "department": "UI Team", "required_skills": ["React"]},
        {"id": "vac_3", "vacancy_id": 3, "title": "DevOps Kubernetes Engineer", "department": "Infrastructure", "required_skills": ["Kubernetes"]},
        {"id": "vac_4", "vacancy_id": 4, "title": "HR Talent Specialist", "department": "People", "required_skills": ["Recruiting"]},
    ]

    mock_emb = [0.1] * 768

    with patch("app.services.vacancy_prefilter.VacancyPreFilter.semantic_vector_search", return_value=["1", "2"]) as mock_stage1:
        # Pass top_k=2
        selected = VacancyPreFilter.filter_vacancies(
            cv_text="Python and React developer with 5 years experience",
            openings=openings,
            top_k=2,
            cv_embedding=mock_emb,
        )

        assert len(selected) <= 2
        # Semantic vector search Stage 1 was invoked
        mock_stage1.assert_called_once()
        selected_ids = {str(j.get("vacancy_id")) for j in selected}
        # Only candidates returned by Stage 1 ("1" or "2") reached Stage 2
        assert selected_ids.issubset({"1", "2"})


def test_fallback_when_embedding_disabled():
    openings = [
        {"id": "vac_1", "vacancy_id": 1, "title": "Python Developer", "department": "Engineering", "required_skills": ["Python"]},
        {"id": "vac_2", "vacancy_id": 2, "title": "Java Developer", "department": "Engineering", "required_skills": ["Java"]},
    ]

    with patch.object(settings, "EMBEDDING_ENABLED", False):
        with patch("app.services.vacancy_prefilter.VacancyPreFilter.semantic_vector_search") as mock_stage1:
            selected = VacancyPreFilter.filter_vacancies(
                cv_text="Python developer",
                openings=openings,
                top_k=1,
            )
            # Stage 1 semantic search skipped when EMBEDDING_ENABLED is False
            assert mock_stage1.call_count == 0
            assert len(selected) == 1


def test_scoring_engine_retains_final_ranking_authority():
    cv_text = "Senior Python Engineer with 6 years experience in FastAPI and PostgreSQL"
    job = {
        "id": "vac_10",
        "vacancy_id": 10,
        "title": "Senior Python Engineer",
        "department": "Backend Engineering",
        "required_skills": ["Python", "FastAPI", "PostgreSQL"],
        "min_experience_years": 5.0,
    }

    match = ScoringEngine.evaluate_job_match(
        cv_text=cv_text,
        job=job,
        candidate_experience=6.0,
    )

    assert match.overall_score > 70.0
    assert match.classification in ("HIGH", "MEDIUM", "LOW")
    assert match.evidence is not None
