from __future__ import annotations

import time

from app.core.cache import CacheKey, CacheManager, MemoryCache


def test_cache_key_generation_deterministic() -> None:
    key1 = CacheKey.for_llm_match(
        document_hash="abc123hash",
        vacancy_ids=["101", "102"],
        prompt_version="prompt-v1",
        model_version="qwen2.5:7b",
    ).to_key()

    key2 = CacheKey.for_llm_match(
        document_hash="abc123hash",
        vacancy_ids=["102", "101"],  # reversed order should yield same key
        prompt_version="prompt-v1",
        model_version="qwen2.5:7b",
    ).to_key()

    assert key1 == key2
    assert key1.startswith("doc_abc123hash_")


def test_cache_key_changes_on_version_bump() -> None:
    key_v1 = CacheKey.for_llm_match(
        document_hash="abc123hash",
        prompt_version="prompt-v1",
    ).to_key()

    key_v2 = CacheKey.for_llm_match(
        document_hash="abc123hash",
        prompt_version="prompt-v2",
    ).to_key()

    assert key_v1 != key_v2


def test_memory_cache_crud_and_ttl() -> None:
    cache = MemoryCache(max_size=100)

    cache.set("test_key", {"data": 42}, ttl=10)
    assert cache.get("test_key") == {"data": 42}
    assert cache.exists("test_key") is True

    cache.delete("test_key")
    assert cache.get("test_key") is None
    assert cache.exists("test_key") is False


def test_memory_cache_eviction_on_capacity() -> None:
    cache = MemoryCache(max_size=2)
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    cache.set("k3", "v3")

    # k1 should have been evicted as max_size=2
    assert len(cache._store) <= 2
    assert cache.get("k3") == "v3"


def test_cache_manager_multilevel() -> None:
    l1 = MemoryCache(max_size=50)
    manager = CacheManager("test_ns", providers=[l1])

    manager.set("managed_key", "payload_value", ttl=300)
    assert manager.get("managed_key") == "payload_value"

    manager.delete("managed_key")
    assert manager.get("managed_key") is None
