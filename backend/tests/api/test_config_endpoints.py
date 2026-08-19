from __future__ import annotations

from unittest.mock import patch
from starlette.testclient import TestClient


def test_get_config_schema(client: TestClient, admin_auth_headers: dict[str, str]) -> None:
    response = client.get("/api/config/schema", headers=admin_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def test_get_system_default_rule_config(client: TestClient, admin_auth_headers: dict[str, str]) -> None:
    response = client.get("/api/config/system-default", headers=admin_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "fields" in data


def test_list_active_rules_with_mock(client: TestClient, admin_auth_headers: dict[str, str]) -> None:
    mock_rules = {"groups": ["name", "location", "scoring"]}
    with patch("app.services.configuration_service.ConfigurationService.list_active_rules", return_value=mock_rules):
        response = client.get("/api/config/rules", headers=admin_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "groups" in data
