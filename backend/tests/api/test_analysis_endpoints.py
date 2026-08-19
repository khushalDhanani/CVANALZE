from __future__ import annotations

from unittest.mock import AsyncMock, patch
from starlette.testclient import TestClient

from app.schemas.match import CandidateMatchAnalysis, JobMatchResult


def test_match_health_endpoint(client: TestClient, admin_auth_headers: dict[str, str]) -> None:
    response = client.get("/api/match/health", headers=admin_auth_headers)
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data


def test_match_analyze_endpoint(
    client: TestClient,
    recruiter_auth_headers: dict[str, str],
    sample_candidate_cv_text: str,
    sample_job_openings: list[dict],
) -> None:
    job_result = JobMatchResult(
        job_id="job-101",
        job_title="Senior Python Developer",
        department="Engineering",
        score=85.0,
        classification="HIGH",
        recommendation="Proceed",
        vacancy_id=101,
    )
    mock_analysis = CandidateMatchAnalysis(
        candidate_name="Alex Mercer",
        suitable_openings=[job_result],
        best_match=job_result,
    )
    with patch("app.services.match_service.MatchService.analyze_single_cv", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = mock_analysis

        payload = {
            "cv_text": sample_candidate_cv_text,
            "job_openings": sample_job_openings,
            "candidate_id": "cand_alex_mercer",
        }
        response = client.post("/api/match/analyze", json=payload, headers=recruiter_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["candidate_name"] == "Alex Mercer"
        assert len(data["suitable_openings"]) == 1


def test_match_status_not_found(client: TestClient, recruiter_auth_headers: dict[str, str]) -> None:
    response = client.get("/api/match/status/unknown_cv_key_12345", headers=recruiter_auth_headers)
    assert response.status_code == 404
