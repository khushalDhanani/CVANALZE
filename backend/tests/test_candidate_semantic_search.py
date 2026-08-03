from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.cache import (
    embedding_cache_manager,
    match_result_cache_manager,
    vacancy_cache_manager,
)
from app.main import app
from app.schemas.candidate_search import CandidateSearchRequest
from app.services.candidate_search_service import CandidateSearchService

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


def test_candidate_semantic_query_vector_ranking():
    mock_results = [
        {
            "id": "cand_1",
            "filename": "john_doe.pdf",
            "markdown": "# John Doe\n\nSenior Python Backend Developer with 6 years experience in FastAPI, PostgreSQL, Microservices.",
            "match_analysis": {
                "primary_department": "Engineering",
                "best_match": {"job_title": "Python Engineer", "score": 92.0},
            },
            "quality_metrics": {"experience_years": 6.0},
            "resume_json": {
                "contact_info": {"name": "John Doe"},
                "skills": ["Python", "FastAPI", "PostgreSQL"],
            },
        },
        {
            "id": "cand_2",
            "filename": "jane_smith.pdf",
            "markdown": "# Jane Smith\n\nFrontend React UI Specialist with 4 years experience in CSS, Tailwind, TypeScript.",
            "match_analysis": {
                "primary_department": "UI",
                "best_match": {"job_title": "React Developer", "score": 88.0},
            },
            "quality_metrics": {"experience_years": 4.0},
            "resume_json": {
                "contact_info": {"name": "Jane Smith"},
                "skills": ["React", "CSS", "Tailwind"],
            },
        },
    ]

    mock_query_emb = [0.5] * 768

    def mock_pg_vector(query_emb, top_k=200):
        # cand_1 has higher vector similarity for python backend query
        return {"cand_1": 0.91, "cand_2": 0.35}

    with (
        patch(
            "app.repositories.result.ResultRepository.list_all_results",
            return_value=mock_results,
        ),
        patch(
            "app.services.embedding_service.EmbeddingService.generate_embedding",
            return_value=mock_query_emb,
        ),
        patch(
            "app.services.candidate_search_service.CandidateSearchService._vector_search_pg",
            side_effect=mock_pg_vector,
        ),
    ):
        req = CandidateSearchRequest(query="Python backend engineer with FastAPI")
        response = CandidateSearchService.search_candidates(req)

        assert response.search_mode == "semantic"
        assert response.total_found == 2
        assert response.candidates[0].id == "cand_1"
        assert response.candidates[0].similarity_score == 0.91
        assert response.candidates[1].id == "cand_2"
        assert response.candidates[1].similarity_score == 0.35


def test_combined_vector_and_structured_filters():
    mock_results = [
        {
            "id": "cand_10",
            "filename": "alice.pdf",
            "markdown": "Python Engineer with 5 years experience.",
            "match_analysis": {"primary_department": "Engineering"},
            "quality_metrics": {"experience_years": 5.0},
            "resume_json": {"skills": ["Python"]},
        },
        {
            "id": "cand_20",
            "filename": "bob.pdf",
            "markdown": "Python Engineer with 1 year experience.",
            "match_analysis": {"primary_department": "Engineering"},
            "quality_metrics": {"experience_years": 1.0},
            "resume_json": {"skills": ["Python"]},
        },
    ]

    with (
        patch(
            "app.repositories.result.ResultRepository.list_all_results",
            return_value=mock_results,
        ),
        patch(
            "app.services.embedding_service.EmbeddingService.generate_embedding",
            return_value=[0.1] * 768,
        ),
        patch(
            "app.services.candidate_search_service.CandidateSearchService._vector_search_pg",
            return_value={"cand_10": 0.88, "cand_20": 0.85},
        ),
    ):
        # Apply experience filter min_experience=3.0
        req = CandidateSearchRequest(
            query="Python developer",
            min_experience=3.0,
            department="Engineering",
        )
        response = CandidateSearchService.search_candidates(req)

        assert response.total_found == 1
        assert response.candidates[0].id == "cand_10"


def test_candidates_search_api_post_endpoint():
    mock_results = [
        {
            "id": "cand_test",
            "filename": "test_cv.pdf",
            "markdown": "FastAPI developer",
            "match_analysis": {"primary_department": "Engineering"},
            "resume_json": {"contact_info": {"name": "Test Candidate"}},
        }
    ]

    with patch(
        "app.repositories.result.ResultRepository.list_all_results",
        return_value=mock_results,
    ):
        resp = client.post(
            "/api/candidates/search",
            json={"query": "FastAPI developer", "limit": 10},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "candidates" in data
        assert data["total_found"] >= 0


def test_candidates_get_endpoint_semantic_query():
    mock_results = [
        {
            "id": "cand_get",
            "filename": "get_cv.pdf",
            "markdown": "Data scientist",
            "match_analysis": {"primary_department": "Data"},
            "resume_json": {"contact_info": {"name": "Data Scientist"}},
        }
    ]

    with patch(
        "app.repositories.result.ResultRepository.list_all_results",
        return_value=mock_results,
    ):
        resp = client.get("/api/candidates?query=Data+scientist")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
