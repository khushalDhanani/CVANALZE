from __future__ import annotations

import io
from starlette.testclient import TestClient


def test_list_processing_jobs(client: TestClient, recruiter_auth_headers: dict[str, str]) -> None:
    response = client.get("/api/cv/processing-jobs", headers=recruiter_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_cv_upload_unsupported_file_extension(client: TestClient, recruiter_auth_headers: dict[str, str]) -> None:
    fake_file = io.BytesIO(b"executable payload")
    files = {"file": ("malicious.exe", fake_file, "application/x-msdownload")}
    response = client.post("/api/cv/upload", files=files, headers=recruiter_auth_headers)
    # Unsupported file extensions should be rejected
    assert response.status_code in (400, 415, 422)


def test_cv_status_not_found(client: TestClient, recruiter_auth_headers: dict[str, str]) -> None:
    response = client.get("/api/cv/status/non_existent_cv_key_9999", headers=recruiter_auth_headers)
    assert response.status_code == 404
