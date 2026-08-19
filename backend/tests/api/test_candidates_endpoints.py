from __future__ import annotations

from unittest.mock import patch
from starlette.testclient import TestClient

from app.schemas.candidate_search import CandidateSearchResponse


def test_list_candidates_empty_or_ok(client: TestClient, recruiter_auth_headers: dict[str, str]) -> None:
    response = client.get("/api/candidates", headers=recruiter_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_search_candidates_post(client: TestClient, recruiter_auth_headers: dict[str, str]) -> None:
    mock_resp = CandidateSearchResponse(
        total_found=0,
        search_mode="keyword",
        query="Senior Python Developer",
        candidates=[],
    )
    with patch("app.services.candidate_search_service.CandidateSearchService.search_candidates", return_value=mock_resp):
        payload = {"query": "Senior Python Developer", "min_experience": 2.0}
        response = client.post("/api/candidates/search", json=payload, headers=recruiter_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total_found"] == 0
        assert data["candidates"] == []


def test_get_candidate_by_id_not_found(client: TestClient, recruiter_auth_headers: dict[str, str]) -> None:
    response = client.get("/api/candidates/non_existent_candidate_999", headers=recruiter_auth_headers)
    assert response.status_code == 404
