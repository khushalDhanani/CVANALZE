from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.cache import (
    embedding_cache_manager,
    match_result_cache_manager,
    vacancy_cache_manager,
)
from app.main import app
from app.schemas.scoring_config import ScoringConfig
from app.services.match_evaluators import RecommendationEvaluator
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
            "strengths": [
                "Strong Python FastAPI expertise",
                "Database design with PostgreSQL",
            ],
            "best_match": {
                "job_title": "Senior Python Developer",
                "department": "Engineering",
                "overall_score": 92.0,
                "missing_skills": ["Docker"],
                "missing_criteria": ["Missing Docker experience"],
            },
            "suitable_openings": [
                {
                    "vacancy_id": 101,
                    "job_title": "Senior Python Developer",
                    "department": "Engineering",
                    "score": 92.0,
                    "classification": "HIGH",
                    "recommendation": "STRONG_MATCH",
                    "missing_skills": ["Docker"],
                }
            ],
        },
        "resume_json": {
            "contact_info": {"name": "Jordan Lee", "email": "jordan@example.com"},
            "skills": ["Python", "FastAPI", "PostgreSQL", "Redis"],
            "certifications": [],
        },
    }

    mock_jobs = [
        {
            "id": 101,
            "vacancy_id": 101,
            "title": "Senior Python Developer",
            "department": "Engineering",
            "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            "QualificationReq": "AWS Certified Solutions Architect preferred",
        },
        {
            "id": 102,
            "vacancy_id": 102,
            "title": "Cloud Infrastructure Engineer",
            "department": "Infrastructure",
            "required_skills": ["Python", "PostgreSQL", "Terraform", "AWS"],
            "QualificationReq": "AWS Certified SysOps Administrator",
        },
    ]

    with (
        patch(
            "app.repositories.result.ResultRepository.read_result_by_filename",
            return_value=mock_result,
        ),
        patch("app.repositories.job.JobRepository.get_all_jobs", return_value=mock_jobs),
    ):
        recs = RecommendationService.get_candidate_recommendations("rec_cand_1")

        assert recs["candidate_id"] == "rec_cand_1"
        assert recs["full_name"] == "Jordan Lee"
        assert len(recs["strengths"]) > 0
        assert recs["overall_match_confidence"] == 92.0
        assert len(recs["best_vacancies"]) > 0
        assert len(recs["related_skills"]) >= 0
        assert len(recs["missing_qualifications"]) > 0
        assert len(recs["recommended_certifications"]) > 0
        assert len(recs["career_transitions"]) > 0
        assert recs["career_transitions"][0]["feasibility_score"] >= 40.0
        assert len(recs["talent_pools"]) > 0
        assert len(recs["actionable_suggestions"]) > 0


def test_candidate_recommendations_empty_state():
    """
    Verifies clean empty state response when candidate analysis has no data or is processing.
    """
    with patch(
        "app.repositories.result.ResultRepository.read_result_by_filename",
        return_value=None,
    ):
        recs = RecommendationService.get_candidate_recommendations("non_existent_cand")

        assert recs["candidate_id"] == "non_existent_cand"
        assert recs["best_vacancies"] == []
        assert recs["missing_qualifications"] == []
        assert recs["recommended_certifications"] == []
        assert recs["career_transitions"] == []
        assert recs["talent_pools"] == []


def test_score_below_configured_strong_threshold_is_not_high_match():
    result = RecommendationEvaluator.evaluate(
        final_score=77.3,
        component_coverage=1.0,
        scoring_config=ScoringConfig(match_high_threshold=80.0, match_medium_threshold=50.0),
    )

    assert result.classification != "HIGH"


def test_no_strong_match_cannot_coexist_with_genuine_match_summary():
    weak_result = {
        "id": "weak_candidate",
        "match_analysis": {
            "has_genuine_match": True,
            "active_vacancy_summary": "Genuine Match Found: stale summary",
            "primary_department": "Rejected Department",
            "suitable_job_roles": ["Evidence-Supported Industry Role"],
            "suitable_openings": [
                {
                    "vacancy_id": 77,
                    "job_title": "Unrelated Vacancy",
                    "department": "Rejected Department",
                    "score": 77.3,
                    "classification": "HIGH",
                }
            ],
        },
        "resume_json": {"contact_info": {"name": "Weak Candidate"}, "skills": []},
    }

    with (
        patch("app.repositories.result.ResultRepository.read_result_by_filename", return_value=weak_result),
        patch("app.repositories.job.JobRepository.get_all_jobs", return_value=[{"id": 77, "title": "Unrelated Vacancy"}]),
        patch("app.services.recommendation_service.ScoringConfig.load", return_value=ScoringConfig(match_high_threshold=80.0)),
    ):
        recs = RecommendationService.get_candidate_recommendations("weak_candidate")

    assert recs["hiring_recommendation"] == "NO_STRONG_MATCH"
    assert "Genuine Match Found" not in str(recs)
    assert recs["best_vacancies"] == []
    assert recs["primary_department"] == ""
    assert recs["industry_role"] == "Evidence-Supported Industry Role"


def test_rejected_departments_do_not_create_talent_pool_assignments():
    rejected_result = {
        "id": "rejected_candidate",
        "match_analysis": {
            "primary_department": "Rejected Department",
            "suitable_openings": [
                {
                    "vacancy_id": 78,
                    "department": "Rejected Department",
                    "score": 77.3,
                    "classification": "HIGH",
                }
            ],
        },
        "resume_json": {"contact_info": {"name": "Rejected Candidate"}, "skills": ["Documented Skill"]},
    }

    with (
        patch("app.repositories.result.ResultRepository.list_all_results", return_value=[rejected_result]),
        patch("app.services.recommendation_service.ScoringConfig.load", return_value=ScoringConfig(match_high_threshold=80.0)),
    ):
        pools = RecommendationService.get_internal_talent_pools()

    assert pools["total_pools"] == 0
    assert pools["talent_pools"] == []


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
