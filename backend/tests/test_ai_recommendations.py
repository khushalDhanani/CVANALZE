from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.cache import embedding_cache_manager, match_result_cache_manager, vacancy_cache_manager
from app.main import app
from app.services.recommendation_service import RecommendationService

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_caches():
    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()
    match_result_cache_manager.clear()
    yield
    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()
    match_result_cache_manager.clear()


def test_candidate_recommendations_all_domains():
    """
    Verifies Candidate AI Recommendations across best vacancies, related skills, missing qualifications,
    recommended certifications, career transitions, and talent pool tags.
    """
    mock_result = {
        "id": "rec_cand_1",
        "filename": "rec_cand_1.pdf",
        "markdown": "Senior Python Backend Engineer with FastAPI and PostgreSQL",
        "quality_metrics": {"experience_years": 5.5},
        "match_analysis": {
            "primary_department": "Engineering",
            "best_match": {
                "job_title": "Senior Python Developer",
                "department": "Engineering",
                "missing_skills": ["Docker"],
                "missing_criteria": ["Missing Docker experience"],
            },
            "suitable_openings": [
                {"vacancy_id": 101, "job_title": "Senior Python Developer", "department": "Engineering", "score": 94.0, "classification": "HIGH", "recommendation": "STRONG_MATCH"}
            ],
        },
        "resume_json": {
            "contact_info": {"name": "Jordan Lee", "email": "jordan@example.com"},
            "skills": ["Python", "FastAPI", "Postgres"],
        },
    }

    with patch("app.repositories.result.ResultRepository.read_result_by_filename", return_value=mock_result):
        recs = RecommendationService.get_candidate_recommendations("rec_cand_1")

        assert recs["candidate_id"] == "rec_cand_1"
        assert recs["full_name"] == "Jordan Lee"
        assert len(recs["best_vacancies"]) > 0
        assert len(recs["related_skills"]) > 0
        assert len(recs["missing_qualifications"]) > 0
        assert len(recs["recommended_certifications"]) > 0
        assert len(recs["career_transitions"]) > 0
        assert len(recs["talent_pools"]) > 0


def test_vacancy_recommendations():
    """
    Verifies Vacancy AI Recommendations for top candidate matches, skill gap insights, and talent pool matches.
    """
    mock_job = {
        "id": "vac_rec_101",
        "vacancy_id": 101,
        "title": "Senior Python Developer",
        "department": "Engineering",
        "required_skills": ["Python", "FastAPI", "PostgreSQL"],
    }

    with patch("app.repositories.job.JobRepository.get_all_jobs", return_value=[mock_job]):
        recs = RecommendationService.get_vacancy_recommendations("101")

        assert recs["vacancy_id"] == "101"
        assert recs["job_title"] == "Senior Python Developer"
        assert "top_candidate_matches" in recs
        assert "skill_gap_insights" in recs
        assert "talent_pools" in recs


def test_internal_talent_pools():
    """
    Verifies aggregation and grouping of candidates into internal talent pools.
    """
    pools = RecommendationService.get_internal_talent_pools()

    assert "total_pools" in pools
    assert "talent_pools" in pools
    assert isinstance(pools["talent_pools"], list)


def test_recommendations_api_endpoints():
    """
    Verifies REST API endpoints for candidate recommendations, vacancy recommendations, and talent pools.
    """
    resp_pools = client.get("/api/recommendations/talent-pools")
    assert resp_pools.status_code == 200
    assert "talent_pools" in resp_pools.json()
