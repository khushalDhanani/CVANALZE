from __future__ import annotations

from starlette.testclient import TestClient


def test_root_endpoint(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Welcome" in data["message"]


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "version" in data


def test_auth_session_lifecycle(client: TestClient) -> None:
    # GET session
    response_get = client.get("/api/auth/session")
    assert response_get.status_code == 200
    data = response_get.json()
    assert "authenticated" in data

    # DELETE session
    response_del = client.delete("/api/auth/session")
    assert response_del.status_code == 200
    data_del = response_del.json()
    assert data_del["authenticated"] is False
