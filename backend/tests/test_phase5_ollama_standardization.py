import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from unittest.mock import MagicMock, call

import httpx
import pytest

from app.core.config import settings
from app.repositories.llm_cache import LLMCacheEntry
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import OllamaLLMService
from app.services.ollama_transport import (
    OllamaModelUnavailableError,
    OllamaSchemaValidationError,
    OllamaTimeoutError,
    OllamaTransport,
    OllamaTransportResult,
)


@pytest.fixture(autouse=True)
def reset_transport(monkeypatch):
    OllamaTransport.close()
    OllamaTransport.reset_metrics()
    EmbeddingService._failed_models_cache.clear()
    monkeypatch.setattr(settings, "LLM_ENABLED", True)
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "OLLAMA_MAX_RETRIES", 1)
    monkeypatch.setattr(settings, "OLLAMA_RETRY_BACKOFF_SECONDS", 0.0)
    yield
    OllamaTransport.close()
    OllamaTransport.reset_metrics()
    EmbeddingService._failed_models_cache.clear()


def _response(data: dict, status_code: int = 200) -> MagicMock:
    normalized = dict(data)
    if "response" in normalized:
        normalized.setdefault("model", settings.OLLAMA_MODEL)
        normalized.setdefault("done", True)
        normalized.setdefault("done_reason", "stop")
    if "embeddings" in normalized:
        normalized.setdefault("model", settings.EMBEDDING_MODEL)
    response = httpx.Response(
        status_code,
        json=normalized,
        request=httpx.Request("POST", "http://ollama.test/api"),
    )
    context = MagicMock()
    context.__enter__.return_value = response
    context.__exit__.return_value = False
    return context


def _install_client(monkeypatch, *side_effects) -> MagicMock:
    client = MagicMock()
    queued = iter(side_effects)

    def stream(_method, _path, **kwargs):
        payload = kwargs.get("json") or {}
        if payload.get("keep_alive") == 0:
            return _response(
                {
                    "model": payload["model"],
                    "response": "",
                    "done": True,
                    "done_reason": "unload",
                }
            )
        item = next(queued)
        if isinstance(item, Exception):
            raise item
        return item

    client.stream.side_effect = stream
    monkeypatch.setattr(OllamaTransport, "get_client", classmethod(lambda cls: client))
    return client


def _disable_cache(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.repositories.llm_cache.LLMCacheRepository.get_cached_entry",
        lambda key: None,
    )
    monkeypatch.setattr(
        "app.repositories.llm_cache.LLMCacheRepository.save_cached_entry",
        lambda key, entry: None,
    )


def test_transport_reuses_one_pooled_client(monkeypatch):
    client = MagicMock()
    client.is_closed = False
    constructor = MagicMock(return_value=client)
    monkeypatch.setattr(httpx, "Client", constructor)
    monkeypatch.setattr(settings, "OLLAMA_LIVE_TESTS_ENABLED", True)

    first = OllamaTransport.get_client()
    second = OllamaTransport.get_client()

    assert first is second
    constructor.assert_called_once()
    timeout = constructor.call_args.kwargs["timeout"]
    assert timeout.read == settings.OLLAMA_REQUEST_TIMEOUT


def test_generation_cache_hit_skips_transport(monkeypatch):
    cached = LLMCacheEntry(
        prompt="cached prompt",
        raw_response="{}",
        structured_data={
            "skill_matches": ["Python"],
            "inferred_skills": [],
            "missing_critical": [],
            "semantic_reason": "Cached analysis",
        },
        reasoning="",
        processing_time_ms=15.0,
        token_count=10,
        inference_time_ms=12,
        model=settings.OLLAMA_MODEL,
        prompt_version="phase5",
    )
    monkeypatch.setattr(
        "app.repositories.llm_cache.LLMCacheRepository.get_cached_entry",
        lambda key: cached,
    )
    execute = MagicMock(side_effect=AssertionError("transport must not run on cache hit"))
    monkeypatch.setattr(OllamaTransport, "execute", execute)

    result = OllamaLLMService.call_qwen("cached", "phase5", "cache-key")

    assert result is not None
    assert result.semantic_reason == "Cached analysis"
    execute.assert_not_called()


def test_transport_retries_connection_error_then_succeeds(monkeypatch):
    request = httpx.Request("GET", "http://ollama.test/api/tags")
    client = _install_client(
        monkeypatch,
        httpx.ConnectError("offline", request=request),
        _response({"models": [{"name": "qwen3:4b"}]}),
    )

    result = OllamaTransport.get_tags()

    assert [model.name for model in result.value.models] == ["qwen3:4b"]
    assert result.attempts == 2
    assert client.stream.call_count == 2
    assert OllamaTransport.get_metrics()["retries"] == 1


def test_transport_uses_exponential_backoff(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_MAX_RETRIES", 2)
    monkeypatch.setattr(settings, "OLLAMA_RETRY_BACKOFF_SECONDS", 0.25)
    sleep = MagicMock()
    monkeypatch.setattr("app.services.ollama_transport.time.sleep", sleep)
    request = httpx.Request("GET", "http://ollama.test/api/tags")
    _install_client(
        monkeypatch,
        httpx.ConnectError("offline", request=request),
        httpx.ConnectError("offline", request=request),
        _response({"models": [{"name": "qwen3:4b"}]}),
    )

    result = OllamaTransport.get_tags()

    assert result.attempts == 3
    assert sleep.call_args_list == [call(0.25), call(0.5)]


def test_transport_applies_uniform_timeout_retries(monkeypatch):
    request = httpx.Request("GET", "http://ollama.test/api/tags")
    client = _install_client(
        monkeypatch,
        httpx.ReadTimeout("slow", request=request),
        httpx.ReadTimeout("slow", request=request),
    )

    with pytest.raises(OllamaTimeoutError):
        OllamaTransport.get_tags()

    metrics = OllamaTransport.get_metrics()
    assert client.stream.call_count == 2
    assert metrics["retries"] == 1
    assert metrics["timeouts"] == 2
    assert metrics["failures"] == 1


def test_invalid_generation_json_returns_fallback_after_retries(monkeypatch):
    _disable_cache(monkeypatch)
    client = _install_client(
        monkeypatch,
        _response({"response": "not structured JSON"}),
        _response({"response": "still not structured JSON"}),
    )

    result = OllamaLLMService.call_qwen("analyze", "phase5", "invalid-json")

    assert result is None
    assert client.stream.call_count == 3
    assert client.stream.call_args_list[-1].kwargs["json"]["keep_alive"] == 0


def test_generation_schema_failure_returns_fallback_after_retries(monkeypatch):
    _disable_cache(monkeypatch)
    invalid_schema = json.dumps({"skill_matches": ["Python"]})
    client = _install_client(
        monkeypatch,
        _response({"response": invalid_schema}),
        _response({"response": invalid_schema}),
    )

    result = OllamaLLMService.call_qwen("analyze", "phase5", "invalid-schema")

    assert result is None
    assert client.stream.call_count == 3
    assert client.stream.call_args_list[-1].kwargs["json"]["keep_alive"] == 0


def test_unavailable_model_is_mapped_without_retry(monkeypatch):
    client = _install_client(monkeypatch, _response({"error": "model not found"}, status_code=404))

    with pytest.raises(OllamaModelUnavailableError):
        OllamaTransport.embed("missing-model", ["resume"])

    assert client.stream.call_count == 2
    assert client.stream.call_args_list[-1].kwargs["json"]["keep_alive"] == 0
    assert OllamaTransport.get_metrics()["retries"] == 0


def test_embedding_service_routes_through_shared_transport(monkeypatch):
    transport_result = OllamaTransportResult(
        value=[[0.1, 0.2, 0.3]],
        response_data={"embeddings": [[0.1, 0.2, 0.3]]},
        duration_ms=5.0,
        attempts=1,
    )
    embed = MagicMock(return_value=transport_result)
    monkeypatch.setattr(OllamaTransport, "embed", embed)

    result = EmbeddingService._call_ollama_embed("embedding-model", "resume")

    assert result == [0.1, 0.2, 0.3]
    embed.assert_called_once_with("embedding-model", ["resume"])


def test_batch_embedding_does_not_fan_out_to_single_inputs(monkeypatch):
    embed = MagicMock(side_effect=OllamaSchemaValidationError("invalid batch", operation="embed"))
    monkeypatch.setattr(OllamaTransport, "embed", embed)

    result = EmbeddingService._call_ollama_batch_embed("embedding-model", ["one", "two"])

    assert result is None
    embed.assert_called_once_with("embedding-model", ["one", "two"])


def test_disabled_llm_returns_fallback_without_transport(monkeypatch):
    _disable_cache(monkeypatch)
    monkeypatch.setattr(settings, "LLM_ENABLED", False)
    execute = MagicMock(side_effect=AssertionError("transport must not run when LLM is disabled"))
    monkeypatch.setattr(OllamaTransport, "execute", execute)

    result = OllamaLLMService.call_qwen("analyze", "phase5", "disabled")

    assert result is None
    execute.assert_not_called()


def test_transport_serializes_parallel_ollama_calls(monkeypatch):
    client = MagicMock()
    state_lock = threading.Lock()
    active = 0
    maximum_active = 0

    @contextmanager
    def stream(_method, _path, **_kwargs):
        nonlocal active, maximum_active
        with state_lock:
            active += 1
            maximum_active = max(maximum_active, active)
        try:
            time.sleep(0.02)
            yield httpx.Response(
                200,
                json={"models": [{"name": "qwen3:4b"}]},
                request=httpx.Request("GET", "http://ollama.test/api/tags"),
            )
        finally:
            with state_lock:
                active -= 1

    client.stream.side_effect = stream
    monkeypatch.setattr(OllamaTransport, "get_client", classmethod(lambda cls: client))

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: OllamaTransport.get_tags(), range(2)))

    assert maximum_active == 1
    assert all(result.value.models[0].name == "qwen3:4b" for result in results)


def test_embedding_rejects_non_finite_values_and_still_unloads(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_EMBEDDING_EXPECTED_DIMENSION", 0)
    
    mock_resp = httpx.Response(
        200,
        text='{"model": "nomic-embed-text", "embeddings": [[NaN, 0.2]]}',
        request=httpx.Request("POST", "http://ollama.test/api"),
    )
    context = MagicMock()
    context.__enter__.return_value = mock_resp
    context.__exit__.return_value = False

    client = _install_client(
        monkeypatch,
        context,
    )

    with pytest.raises(OllamaSchemaValidationError):
        OllamaTransport.embed("nomic-embed-text", ["resume"])

    assert client.stream.call_args_list[-1].kwargs["json"]["keep_alive"] == 0


def test_embedding_chunks_share_one_model_scope_and_unload_once(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_EMBEDDING_EXPECTED_DIMENSION", 0)
    monkeypatch.setattr(settings, "OLLAMA_EMBED_BATCH_SIZE", 1)
    client = _install_client(
        monkeypatch,
        _response({"model": "nomic-embed-text", "embeddings": [[0.1, 0.2]]}),
        _response({"model": "nomic-embed-text", "embeddings": [[0.2, 0.3]]}),
    )

    result = OllamaTransport.embed("nomic-embed-text", ["first", "second"])

    assert result.value == [[0.1, 0.2], [0.2, 0.3]]
    unload_calls = [request_call for request_call in client.stream.call_args_list if request_call.kwargs.get("json", {}).get("keep_alive") == 0]
    assert len(unload_calls) == 1
