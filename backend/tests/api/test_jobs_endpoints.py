from __future__ import annotations

from unittest.mock import patch
from starlette.testclient import TestClient

from app.repositories.job import VacancyLoadResult, VacancyLoadStatus
from app.schemas.job import JobOpening


def test_list_jobs_endpoint(client: TestClient, recruiter_auth_headers: dict[str, str]) -> None:
    mock_jobs = [
        JobOpening(
            id="job-101",
            title="Senior Python Developer",
            department="Engineering",
            required_skills=["Python", "FastAPI"],
        )
    ]
    with patch("app.repositories.job.JobRepository.load_all_jobs") as mock_load:
        mock_load.return_value = VacancyLoadResult(jobs=mock_jobs, status=VacancyLoadStatus.SUCCESS)
        response = client.get("/api/jobs", headers=recruiter_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Senior Python Developer"


def test_invalidate_jobs_cache(client: TestClient, admin_auth_headers: dict[str, str]) -> None:
    with (
        patch("app.repositories.job.JobRepository.invalidate_cache"),
        patch("app.core.tasks.sync_all_vacancies", return_value=None),
    ):
        response = client.post("/api/jobs/cache/invalidate", headers=admin_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


def test_get_job_by_id_not_found(client: TestClient, recruiter_auth_headers: dict[str, str]) -> None:
    with patch("app.repositories.job.JobRepository.get_job_by_id", return_value=None):
        response = client.get("/api/jobs/non_existent_job_9999", headers=recruiter_auth_headers)
        assert response.status_code == 404
