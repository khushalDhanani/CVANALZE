import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.config import SystemConfig
from app.repositories.config import ConfigRepository

client = TestClient(app)


def test_dynamic_config_api():
    """Test the dynamic configuration endpoints."""
    # Simple dictionary to simulate repository state
    fake_store = {"MATCH_HIGH_THRESHOLD": 70.0}

    def fake_get_setting(key, default=None, db=None):
        return fake_store.get(key, default)

    def fake_update_setting(key, value, db=None):
        fake_store[key] = value

    with patch("app.api.config.ConfigRepository.get_setting", side_effect=fake_get_setting), \
         patch("app.api.config.ConfigRepository.update_setting", side_effect=fake_update_setting):
        
        # 1. GET config
        resp = client.get("/api/config/match")
        assert resp.status_code == 200
        data = resp.json()
        assert data["MATCH_HIGH_THRESHOLD"] == 70.0

        # 2. PUT config
        update_payload = {"MATCH_HIGH_THRESHOLD": 85.0}
        resp2 = client.put("/api/config/match", json=update_payload)
        assert resp2.status_code == 200
        updated_data = resp2.json()
        assert updated_data["MATCH_HIGH_THRESHOLD"] == 85.0
