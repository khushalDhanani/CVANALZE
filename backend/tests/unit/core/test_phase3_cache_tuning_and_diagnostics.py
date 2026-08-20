"""
Unit tests for Phase 3 Cache/TTL Tuning & Diagnostic Provenance.

Verifies:
1. CACHE_LRU_CAPACITY and CACHE_VERSION are configured in Settings.
2. CacheManager.get_with_diagnostics() returns cache_hit, cache_source, cache_version, and lookup_time_ms.
3. Cache miss returns cache_hit=False and cache_source='NONE'.
"""

from __future__ import annotations

from unittest.mock import patch

from app.core.cache import CacheManager, MemoryCache
from app.core.config import settings
from app.services.performance_service import EnterprisePerformanceService


def test_cache_settings_configured():
    """Verify CACHE_LRU_CAPACITY and CACHE_VERSION exist in settings."""
    assert hasattr(settings, "CACHE_LRU_CAPACITY")
    assert settings.CACHE_LRU_CAPACITY == 128
    assert hasattr(settings, "CACHE_VERSION")
    assert settings.CACHE_VERSION == "v1.5.0"


def test_cache_manager_get_with_diagnostics_hit_and_miss():
    """Verify get_with_diagnostics tracks cache source, version, and hit/miss status."""
    cm = CacheManager("test_diag_ns", providers=[MemoryCache()], default_ttl=300)
    
    # Test MISS
    val_miss, diag_miss = cm.get_with_diagnostics("missing_key_123", default="fallback")
    assert val_miss == "fallback"
    assert diag_miss["cache_hit"] is False
    assert diag_miss["cache_source"] == "NONE"
    assert diag_miss["cache_namespace"] == "test_diag_ns"
    assert diag_miss["cache_version"] == settings.CACHE_VERSION
    assert "lookup_time_ms" in diag_miss

    # Test HIT
    cm.set("existing_key_123", "cached_val")
    val_hit, diag_hit = cm.get_with_diagnostics("existing_key_123")
    assert val_hit == "cached_val"
    assert diag_hit["cache_hit"] is True
    assert diag_hit["cache_source"] in {"MemoryCache", "RedisCache", "FileCache"}
    assert diag_hit["cache_namespace"] == "test_diag_ns"
    assert diag_hit["cache_version"] == settings.CACHE_VERSION
    assert "lookup_time_ms" in diag_hit


def test_performance_cache_default_ttl_uses_runtime_setting(monkeypatch):
    monkeypatch.setattr(settings, "PERFORMANCE_L1_CACHE_TTL_SECONDS", 17.0)

    with patch.object(EnterprisePerformanceService._l1_cache, "set") as cache_set:
        EnterprisePerformanceService.set_multilevel_cache("candidate", [0.1, 0.2])

    cache_set.assert_called_once_with("candidate", [0.1, 0.2], ttl=17.0)
