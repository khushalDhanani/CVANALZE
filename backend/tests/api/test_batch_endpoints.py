from __future__ import annotations

from starlette.testclient import TestClient


def test_batch_match_candidates_validation_limits(client: TestClient, recruiter_auth_headers: dict[str, str]) -> None:
    # Limit 0 should be rejected
    response = client.post("/api/batch/match-candidates?limit=0", headers=recruiter_auth_headers)
    assert response.status_code == 400

    # Limit exceeding max limit (50) should be rejected
    response_large = client.post("/api/batch/match-candidates?limit=9999", headers=recruiter_auth_headers)
    assert response_large.status_code == 400


def test_get_batch_job_not_found(client: TestClient, recruiter_auth_headers: dict[str, str]) -> None:
    response = client.get("/api/batch/jobs/non_existent_batch_12345", headers=recruiter_auth_headers)
    assert response.status_code == 404
