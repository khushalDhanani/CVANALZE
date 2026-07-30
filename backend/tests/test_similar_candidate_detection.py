from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.cache import embedding_cache_manager, match_result_cache_manager, vacancy_cache_manager
from app.core.config import settings
from app.main import app
from app.services.similar_candidate_service import SimilarCandidateService

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


def test_detect_similar_candidates_above_threshold():
    """
    Verifies detection of similar candidates above threshold (default >= 0.85).
    """
    mock_results = [
        {
            "id": "cand_target",
            "filename": "target_cv.pdf",
            "markdown": "Senior Python Engineer",
            "resume_json": {"contact_info": {"name": "Target Candidate"}},
        },
        {
            "id": "cand_similar",
            "filename": "similar_cv.pdf",
            "markdown": "Senior Python Engineer (Updated version)",
            "match_analysis": {"primary_department": "Engineering", "best_match": {"job_title": "Python Developer"}},
            "resume_json": {"contact_info": {"name": "Similar Candidate", "email": "similar@example.com"}},
        },
        {
            "id": "cand_different",
            "filename": "different_cv.pdf",
            "markdown": "HR Recruiter",
            "match_analysis": {"primary_department": "HR"},
            "resume_json": {"contact_info": {"name": "Different Candidate"}},
        },
    ]

    target_emb = [0.1] * 768

    def mock_vector_pg(cv_key, emb, limit):
        # Return high similarity for cand_similar (0.88), low for cand_different (0.30)
        return {"cand_similar": 0.88, "cand_different": 0.30}

    with patch("app.repositories.result.ResultRepository.list_all_results", return_value=mock_results):
        with patch.object(SimilarCandidateService, "_vector_search_pg", side_effect=mock_vector_pg):
            similar = SimilarCandidateService.detect_similar_candidates(
                cv_key="cand_target",
                cv_embedding=target_emb,
                threshold=0.85,
            )

            assert len(similar) == 1
            assert similar[0]["cv_key"] == "cand_similar"
            assert similar[0]["similarity_score"] == 0.88
            assert similar[0]["is_duplicate_flag"] is False


def test_duplicate_flag_identification():
    """
    Verifies highly similar candidates (>= 0.95) set is_duplicate_flag = True.
    """
    mock_results = [
        {
            "id": "cand_dup",
            "filename": "exact_duplicate.pdf",
            "markdown": "Identical resume text",
            "resume_json": {"contact_info": {"name": "Duplicate Candidate"}},
        }
    ]

    with patch("app.repositories.result.ResultRepository.list_all_results", return_value=mock_results):
        with patch.object(SimilarCandidateService, "_vector_search_pg", return_value={"cand_dup": 0.97}):
            similar = SimilarCandidateService.detect_similar_candidates(
                cv_key="cand_original",
                cv_embedding=[0.1] * 768,
                threshold=0.85,
            )

            assert len(similar) == 1
            assert similar[0]["cv_key"] == "cand_dup"
            assert similar[0]["similarity_score"] == 0.97
            assert similar[0]["is_duplicate_flag"] is True


def test_no_false_merges_records_preserved():
    """
    Verifies original candidate records are preserved independently without merging or deletion.
    """
    mock_results = [
        {"id": "cand_1", "filename": "c1.pdf", "markdown": "Python Dev"},
        {"id": "cand_2", "filename": "c2.pdf", "markdown": "Python Dev copy"},
    ]

    with patch("app.repositories.result.ResultRepository.list_all_results", return_value=mock_results):
        with patch.object(SimilarCandidateService, "_vector_search_pg", return_value={"cand_2": 0.92}):
            _ = SimilarCandidateService.detect_similar_candidates("cand_1", [0.1] * 768)

            # Both records remain intact in mock_results (no deletion/mutation)
            assert len(mock_results) == 2
            assert mock_results[0]["id"] == "cand_1"
            assert mock_results[1]["id"] == "cand_2"


def test_candidate_360_similar_candidates_api():
    """
    Verifies Candidate 360 API GET /api/candidates/{candidate_id} includes similar_candidates payload.
    """
    mock_result = {
        "id": "cand_360",
        "filename": "cand_360.pdf",
        "markdown": "Senior Developer",
        "similar_candidates": [
            {
                "cv_key": "cand_other",
                "similarity_score": 0.89,
                "full_name": "Other Candidate",
                "is_duplicate_flag": False,
            }
        ],
    }

    with patch("app.repositories.result.ResultRepository.read_result_by_filename", return_value=mock_result):
        resp = client.get("/api/candidates/cand_360")
        assert resp.status_code == 200
        data = resp.json()
        assert "similar_candidates" in data
        assert len(data["similar_candidates"]) == 1
        assert data["similar_candidates"][0]["cv_key"] == "cand_other"
