import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.result import ResultRepository
from app.repositories.llm_cache import LLMCacheRepository

client = TestClient(app)


def test_redis_result_repository_caching():
    """Test that ResultRepository uses Redis when configured."""
    mock_redis = MagicMock()
    with patch("app.repositories.result._redis_client", mock_redis):
        mock_data = {"extracted": "content", "pages": 1}
        
        # 1. Test atomic_save_result
        res = ResultRepository.atomic_save_result("test_result.json", mock_data)
        
        # Should return the redis URI string
        assert isinstance(res, str)
        assert res.startswith("redis://")
        
        # Redis commands should be executed
        mock_redis.set.assert_called_once()
        mock_redis.expire.assert_called_once()
        
        # 2. Test read_result using the redis path
        mock_redis.get.return_value = json.dumps(mock_data)
        read_data = ResultRepository.read_result(res)
        assert read_data == mock_data
        
        # 3. Test read_result_by_filename
        mock_redis.get.reset_mock()
        mock_redis.get.return_value = json.dumps(mock_data)
        read_data2 = ResultRepository.read_result_by_filename("test_result.json")
        assert read_data2 == mock_data


def test_redis_llm_repository_caching():
    """Test that LLMCacheRepository uses Redis when configured."""
    mock_redis = MagicMock()
    with patch("app.repositories.llm_cache._redis_client", mock_redis):
        mock_data = {"score": 85.0}
        
        # 1. Test save_result
        LLMCacheRepository.save_result("test-model", "1.0", "test prompt", mock_data)
        mock_redis.set.assert_called_once()
        mock_redis.expire.assert_called_once()
        
        # 2. Test get_cached_result
        mock_redis.get.return_value = json.dumps(mock_data)
        read_data = LLMCacheRepository.get_cached_result("test-model", "1.0", "test prompt")
        assert read_data == mock_data


def test_cv_upload_background_task_returns_processing_status():
    """Test that /cv/upload endpoint immediately returns a processing status, preventing 504 timeouts."""
    # filetype relies on magic bytes, the PDF signature is %PDF-
    pdf_content = b"%PDF-1.4\n" + b"Dummy content"
    
    response = client.post(
        "/api/cv/upload",
        files={"file": ("test_background.pdf", pdf_content, "application/pdf")}
    )
    
    # We should get a 200 OK immediately, instead of waiting for Docling/LLM
    assert response.status_code == 200, response.text
    data = response.json()
    
    # Assert background task response format
    assert data["status"] == "processing"
    assert "cv_key" in data
    assert "message" in data
    
    cv_key = data["cv_key"]
    
    # Assert the status endpoint is functional
    status_response = client.get(f"/api/cv/status/{cv_key}")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["status"] == "processing"
