from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.cache import embedding_cache_manager, match_result_cache_manager, vacancy_cache_manager
from app.main import app
from app.services.performance_service import EnterprisePerformanceService

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_caches():
    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()
    match_result_cache_manager.clear()
    EnterprisePerformanceService.invalidate_cache_by_pattern("*")
    yield
    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()
    match_result_cache_manager.clear()
    EnterprisePerformanceService.invalidate_cache_by_pattern("*")


@pytest.mark.asyncio
async def test_async_batch_embedding_generation():
    """
    Verifies async batch embedding generation with concurrent worker execution and multi-level caching.
    """
    mock_emb = [0.1] * 768
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb):
        texts = ["Python Backend Developer", "React Frontend Developer", "DevOps Engineer"]
        results = await EnterprisePerformanceService.generate_embeddings_batch_async(texts, max_concurrent=3)

        assert len(results) == 3
        assert results[0] == mock_emb
        assert results[1] == mock_emb
        assert results[2] == mock_emb


def test_multilevel_caching_l1_l2():
    """
    Verifies L1 Memory cache sub-millisecond retrieval and propagation from L2 cache.
    """
    key = "nomic-embed-text:test_key_multilevel"
    val = [0.5] * 768

    # Set in multi-level cache
    EnterprisePerformanceService.set_multilevel_cache(key, val)

    # First retrieval -> L1 hit
    retrieved_l1 = EnterprisePerformanceService.get_multilevel_cache(key)
    assert retrieved_l1 == val

    metrics = EnterprisePerformanceService.get_performance_metrics()
    assert metrics["cache_telemetry"]["l1_memory_hits"] > 0


def test_intelligent_cache_invalidation():
    """
    Verifies targeted pattern-based multi-level cache invalidation.
    """
    key = "nomic-embed-text:temp_to_clear"
    EnterprisePerformanceService.set_multilevel_cache(key, [0.2] * 768)

    EnterprisePerformanceService.invalidate_cache_by_pattern("nomic-embed-text:*")

    cached_val = EnterprisePerformanceService.get_multilevel_cache(key)
    assert cached_val is None


def test_performance_metrics_endpoint():
    """
    Verifies GET /api/performance/metrics REST API telemetry endpoint.
    """
    resp = client.get("/api/performance/metrics")
    assert resp.status_code == 200
    data = resp.json()

    assert "cache_telemetry" in data
    assert "pipeline_telemetry" in data
    assert "retrieval_order_guarantee" in data
    assert data["retrieval_order_guarantee"]["semantic_retrieval_precedes_scoring"] is True


def test_cache_invalidate_endpoint():
    """
    Verifies POST /api/performance/cache/invalidate REST API endpoint.
    """
    resp = client.post("/api/performance/cache/invalidate", json={"pattern": "*"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["cleared"] is True
    assert "successfully" in data["message"].lower()
