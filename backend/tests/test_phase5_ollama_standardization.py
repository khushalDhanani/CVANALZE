import json
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
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = data
    return response


def _install_client(monkeypatch, *side_effects) -> MagicMock:
    client = MagicMock()
    client.request.side_effect = list(side_effects)
    monkeypatch.setattr(OllamaTransport, "get_client", classmethod(lambda cls: client))
    return client


def _disable_cache(monkeypatch) -> None:
    monkeypatch.setattr("app.repositories.llm_cache.LLMCacheRepository.get_cached_entry", lambda key: None)
    monkeypatch.setattr("app.repositories.llm_cache.LLMCacheRepository.save_cached_entry", lambda key, entry: None)


def test_transport_reuses_one_pooled_client(monkeypatch):
    client = MagicMock()
    client.is_closed = False
    constructor = MagicMock(return_value=client)
    monkeypatch.setattr(httpx, "Client", constructor)

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
    monkeypatch.setattr("app.repositories.llm_cache.LLMCacheRepository.get_cached_entry", lambda key: cached)
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
    assert client.request.call_count == 2
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
    assert client.request.call_count == 2
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
    assert client.request.call_count == 2


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
    assert client.request.call_count == 2


def test_unavailable_model_is_mapped_without_retry(monkeypatch):
    client = _install_client(monkeypatch, _response({"error": "model not found"}, status_code=404))

    with pytest.raises(OllamaModelUnavailableError):
        OllamaTransport.embed("missing-model", ["resume"])

    assert client.request.call_count == 1
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


def test_batch_embedding_preserves_single-input_fallback(monkeypatch):
    first = OllamaTransportResult(
        value=[[0.1]],
        response_data={"embeddings": [[0.1]]},
        duration_ms=5.0,
        attempts=1,
    )
    second = OllamaTransportResult(
        value=[[0.3]],
        response_data={"embeddings": [[0.3]]},
        duration_ms=3.0,
        attempts=1,
    )
    embed = MagicMock(
        side_effect=[
            OllamaSchemaValidationError("invalid batch", operation="embed"),
            first,
            second,
        ]
    )
    monkeypatch.setattr(OllamaTransport, "embed", embed)

    result = EmbeddingService._call_ollama_batch_embed("embedding-model", ["one", "two"])

    assert result == [[0.1], [0.3]]
    assert embed.call_args_list == [
        call("embedding-model", ["one", "two"]),
        call("embedding-model", ["one"]),
        call("embedding-model", ["two"]),
    ]


def test_disabled_llm_returns_fallback_without_transport(monkeypatch):
    _disable_cache(monkeypatch)
    monkeypatch.setattr(settings, "LLM_ENABLED", False)
    execute = MagicMock(side_effect=AssertionError("transport must not run when LLM is disabled"))
    monkeypatch.setattr(OllamaTransport, "execute", execute)

    result = OllamaLLMService.call_qwen("analyze", "phase5", "disabled")

    assert result is None
    execute.assert_not_called()
