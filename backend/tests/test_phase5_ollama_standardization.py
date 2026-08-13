import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, call

import httpx
import pytest
from fastapi import HTTPException

from app.api.analysis import analyze_cv_text, check_llm_health
from app.core import lifecycle
from app.core.config import Settings, settings
from app.repositories.llm_cache import LLMCacheEntry
from app.schemas.cv import CVMatchRequest
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import OllamaLLMService
from app.services.ollama_transport import (
    OllamaCircuitOpenError,
    OllamaError,
    OllamaHTTPError,
    OllamaInvalidResponseError,
    OllamaModelUnavailableError,
    OllamaSchemaValidationError,
    OllamaTimeoutError,
    OllamaTransport,
    OllamaTransportResult,
    OllamaUnavailableError,
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
    monkeypatch.setattr(settings, "OLLAMA_RETRY_JITTER_SECONDS", 0.0)
    monkeypatch.setattr(settings, "OLLAMA_RESIDENCY_ENABLED", False)
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


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"OLLAMA_BASE_URL": "localhost:11434"}, "OLLAMA_BASE_URL"),
        ({"OLLAMA_MODEL": ""}, "OLLAMA_MODEL"),
        ({"OLLAMA_GENERATE_TIMEOUT_SECONDS": 0}, "timeouts must be greater than zero"),
        ({"OLLAMA_MAX_RETRIES": -1}, "retry count"),
        ({"OLLAMA_GENERATION_NUM_PREDICT": 4096}, "OLLAMA_GENERATION_NUM_PREDICT"),
    ],
)
def test_settings_reject_invalid_ollama_configuration(overrides, message):
    with pytest.raises(ValueError, match=message):
        Settings(_env_file=None, **{"OLLAMA_BASE_URL": "http://localhost:11434", **overrides})


def test_model_availability_uses_exact_canonical_names():
    assert OllamaTransport.is_model_available("nomic-embed-text", ["nomic-embed-text:latest"])
    assert OllamaTransport.is_model_available("LLAMA3.2:3B", ["llama3.2:3b"])
    assert not OllamaTransport.is_model_available("llama3.2:3b", ["llama3.2:3b-instruct"])


def test_status_requires_every_enabled_configured_model(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "generation-model")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "embedding-model")
    _install_client(
        monkeypatch,
        _response({"models": [{"name": "generation-model"}, {"name": "embedding-model:latest"}]}),
    )

    is_ready, model_names = OllamaLLMService.get_status()

    assert is_ready is True
    assert model_names == ["generation-model", "embedding-model:latest"]


def test_status_is_not_ready_when_generation_model_is_missing(monkeypatch, caplog):
    caplog.set_level("ERROR", logger="cv_analyzer")
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "missing-generation-model")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "embedding-model")
    _install_client(monkeypatch, _response({"models": [{"name": "embedding-model:latest"}]}))

    is_ready, model_names = OllamaLLMService.get_status()

    assert is_ready is False
    assert model_names == ["embedding-model:latest"]
    assert "status=MODEL_MISSING" in caplog.text
    assert "missing-generation-model" in caplog.text


@pytest.mark.asyncio
async def test_llm_health_reports_reachable_configuration_error_for_missing_model(monkeypatch):
    monkeypatch.setattr(settings, "LLM_ENABLED", True)
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "missing-generation-model")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "embedding-model")
    monkeypatch.setattr(
        OllamaLLMService,
        "get_status",
        classmethod(lambda cls: (False, ["embedding-model:latest"])),
    )

    payload = await check_llm_health()

    assert payload["status"] == "configuration_error"
    assert payload["model_available"] is False
    assert payload["embedding_model_available"] is True
    assert payload["missing_models"] == ["missing-generation-model"]
    assert payload["available_models"] == ["embedding-model:latest"]


def test_production_startup_rejects_unavailable_configured_model(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "LLM_ENABLED", True)
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", False)
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "llama3.2:3b")
    monkeypatch.setattr(OllamaLLMService, "get_available_models", classmethod(lambda cls: ["llama3.2:3b-instruct"]))

    with pytest.raises(RuntimeError, match="llama3.2:3b.*unavailable"):
        lifecycle.verify_ollama_models()


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
        _response({"models": [{"name": "llama3.2:3b"}]}),
    )

    result = OllamaTransport.get_tags()

    assert [model.name for model in result.value.models] == ["llama3.2:3b"]
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
        _response({"models": [{"name": "llama3.2:3b"}]}),
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

    with pytest.raises(OllamaTimeoutError) as exc_info:
        OllamaTransport.get_tags()

    assert exc_info.value.operation == "tags"
    assert exc_info.value.retryable is True
    assert exc_info.value.status_code is None
    assert exc_info.value.detail == "slow"
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


def test_length_terminated_generation_is_never_accepted(monkeypatch, caplog):
    caplog.set_level("WARNING", logger="cv_analyzer")
    _disable_cache(monkeypatch)
    incomplete = json.dumps({"skill_matches": [], "inferred_skills": [], "missing_critical": [], "semantic_reason": "partial"})
    client = _install_client(
        monkeypatch,
        _response({"response": incomplete, "done_reason": "length"}),
        _response({"response": incomplete, "done_reason": "length"}),
    )

    result = OllamaLLMService.call_qwen("analyze", "phase5", "length-stop")

    assert result is None
    assert client.stream.call_count == 2
    assert "status=OUTPUT_LIMIT" in caplog.text
    assert "response_chars=" in caplog.text
    assert f"num_predict={settings.OLLAMA_GENERATION_NUM_PREDICT}" in caplog.text


def test_generation_rejects_unload_completion_reason_before_parser(monkeypatch):
    client = _install_client(
        monkeypatch,
        _response({"model": settings.OLLAMA_MODEL, "response": "{}", "done": True, "done_reason": "unload"}),
    )
    parser = MagicMock(return_value={})
    payload = OllamaTransport.build_generation_payload(
        model=settings.OLLAMA_MODEL,
        prompt="analyze",
        response_schema={"type": "object"},
        think=None,
        options={},
    )

    with pytest.raises(OllamaSchemaValidationError, match="invalid completion reason") as exc_info:
        OllamaTransport.generate(operation="test_generation", payload=payload, parser=parser)

    assert exc_info.value.retryable is False
    assert exc_info.value.detail == "unload"
    parser.assert_not_called()
    assert client.stream.call_count == 2


def test_generation_uses_prompt_oriented_generate_endpoint_and_payload(monkeypatch):
    client = _install_client(monkeypatch, _response({"response": "{}"}))
    response_schema = {"type": "object", "properties": {"result": {"type": "string"}}}
    options = {"temperature": 0.0, "num_ctx": 4096}
    payload = OllamaTransport.build_generation_payload(
        model=settings.OLLAMA_MODEL,
        prompt="Analyze this CV",
        response_schema=response_schema,
        think=True,
        options=options,
    )

    result = OllamaTransport.generate(
        operation="test_generation_contract",
        payload=payload,
        parser=lambda data: data["response"],
    )

    generation_request = client.stream.call_args_list[0]
    assert generation_request.args == ("POST", "/api/generate")
    assert "/api/chat" not in [request.args[1] for request in client.stream.call_args_list]
    assert generation_request.kwargs["json"] == {
        "model": settings.OLLAMA_MODEL,
        "prompt": "Analyze this CV",
        "format": response_schema,
        "stream": False,
        "keep_alive": settings.OLLAMA_KEEP_ALIVE,
        "options": options,
        "think": True,
    }
    assert result.value == "{}"


def test_non_streaming_response_is_joined_before_single_json_decode(monkeypatch):
    response = MagicMock()
    response.status_code = 200
    response.headers = {}
    response.iter_bytes.return_value = iter(
        [
            b'{"models":[',
            b'{"name":"llama3.2:3b",',
            b'"digest":"sha256:test"}',
            b']}',
        ]
    )
    context = MagicMock()
    context.__enter__.return_value = response
    context.__exit__.return_value = False
    client = _install_client(monkeypatch, context)

    result = OllamaTransport.get_tags()

    assert [model.name for model in result.value.models] == ["llama3.2:3b"]
    assert result.value.models[0].digest == "sha256:test"
    assert client.stream.call_args.args == ("GET", "/api/tags")
    response.iter_bytes.assert_called_once_with()


def test_residency_policy_keeps_model_loaded(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_RESIDENCY_ENABLED", True)
    monkeypatch.setattr(settings, "OLLAMA_EMBEDDING_EXPECTED_DIMENSION", 0)
    client = _install_client(monkeypatch, _response({"model": settings.EMBEDDING_MODEL, "embeddings": [[0.1, 0.2]]}))

    OllamaTransport.embed(settings.EMBEDDING_MODEL, ["resume"])

    unload_calls = [request_call for request_call in client.stream.call_args_list if request_call.kwargs.get("json", {}).get("keep_alive") == 0]
    assert unload_calls == []
    assert OllamaTransport.get_metrics()["residency_skips"] == 1


def test_circuit_breaker_fails_fast_after_threshold(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_MAX_RETRIES", 0)
    monkeypatch.setattr(settings, "OLLAMA_CIRCUIT_BREAKER_FAILURE_THRESHOLD", 2)
    monkeypatch.setattr(settings, "OLLAMA_CIRCUIT_BREAKER_RESET_SECONDS", 30.0)
    request = httpx.Request("GET", "http://ollama.test/api/tags")
    client = _install_client(
        monkeypatch,
        httpx.ConnectError("offline", request=request),
        httpx.ConnectError("offline", request=request),
    )

    with pytest.raises(OllamaUnavailableError):
        OllamaTransport.get_tags()
    with pytest.raises(OllamaUnavailableError):
        OllamaTransport.get_tags()
    with pytest.raises(OllamaCircuitOpenError):
        OllamaTransport.get_tags()

    assert client.stream.call_count == 2
    assert OllamaTransport.get_metrics()["circuit_rejections"] == 1


def test_unavailable_model_is_mapped_without_retry(monkeypatch):
    client = _install_client(monkeypatch, _response({"error": "model not found"}, status_code=404))

    with pytest.raises(OllamaModelUnavailableError):
        OllamaTransport.embed("missing-model", ["resume"])

    assert client.stream.call_count == 2
    assert client.stream.call_args_list[-1].kwargs["json"]["keep_alive"] == 0
    assert OllamaTransport.get_metrics()["retries"] == 0


def test_generation_model_unavailable_propagates_instead_of_returning_fallback(monkeypatch, caplog):
    caplog.set_level("ERROR", logger="cv_analyzer")
    _disable_cache(monkeypatch)
    error = OllamaModelUnavailableError(settings.OLLAMA_MODEL, operation="qwen_analysis", detail="model not found")
    generate = MagicMock(side_effect=error)
    trace = MagicMock()
    monkeypatch.setattr(OllamaTransport, "generate", generate)
    monkeypatch.setattr(OllamaLLMService, "_trace", trace)

    with pytest.raises(OllamaModelUnavailableError) as exc_info:
        OllamaLLMService.call_qwen("analyze", "phase5", "missing-model")

    assert exc_info.value is error
    assert exc_info.value.status_code == 404
    assert exc_info.value.retryable is False
    assert exc_info.value.detail == "model not found"
    assert "status=PROPAGATED" in caplog.text
    assert "status=FALLBACK" not in caplog.text
    assert trace.call_args.kwargs["fallback_used"] is False
    assert trace.call_args.kwargs["error_class"] == "OllamaModelUnavailableError"
    generate.assert_called_once()


@pytest.mark.parametrize(
    "error",
    [
        OllamaTimeoutError("request timed out", operation="qwen_analysis", detail="read deadline exceeded"),
        OllamaUnavailableError("service unavailable", operation="qwen_analysis", detail="connection refused"),
        OllamaHTTPError("server unavailable", operation="qwen_analysis", status_code=503, retryable=True, detail="overloaded"),
    ],
)
def test_generation_operational_failures_propagate_instead_of_returning_fallback(monkeypatch, caplog, error):
    caplog.set_level("ERROR", logger="cv_analyzer")
    _disable_cache(monkeypatch)
    generate = MagicMock(side_effect=error)
    trace = MagicMock()
    monkeypatch.setattr(OllamaTransport, "generate", generate)
    monkeypatch.setattr(OllamaLLMService, "_trace", trace)

    with pytest.raises(type(error)) as exc_info:
        OllamaLLMService.call_qwen("analyze", "phase5", "infrastructure-failure")

    assert exc_info.value is error
    assert "status=PROPAGATED" in caplog.text
    assert "status=FALLBACK" not in caplog.text
    assert trace.call_args.kwargs["fallback_used"] is False
    assert trace.call_args.kwargs["error_class"] == type(error).__name__
    generate.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_api_maps_generation_model_unavailable_to_503(monkeypatch):
    error = OllamaModelUnavailableError(settings.OLLAMA_MODEL, operation="optimized_match", detail="model not found")
    analyze = AsyncMock(side_effect=error)
    monkeypatch.setattr("app.api.analysis.MatchService.analyze_single_cv", analyze)

    with pytest.raises(HTTPException) as exc_info:
        await analyze_cv_text(CVMatchRequest(cv_text="Senior Python developer"))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == f"Configured LLM model '{settings.OLLAMA_MODEL}' is unavailable."
    analyze.assert_awaited_once_with("Senior Python developer")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (OllamaTimeoutError("request timed out", operation="optimized_match"), 504, "LLM generation timed out."),
        (OllamaUnavailableError("connection refused", operation="optimized_match"), 503, "LLM service is unavailable."),
        (OllamaHTTPError("server unavailable", operation="optimized_match", status_code=503, retryable=True), 503, "LLM service is unavailable."),
    ],
)
async def test_analyze_api_maps_operational_failures(monkeypatch, error, expected_status, expected_detail):
    analyze = AsyncMock(side_effect=error)
    monkeypatch.setattr("app.api.analysis.MatchService.analyze_single_cv", analyze)

    with pytest.raises(HTTPException) as exc_info:
        await analyze_cv_text(CVMatchRequest(cv_text="Senior Python developer"))

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail == expected_detail


def test_http_error_preserves_bounded_sanitized_ollama_detail(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_MAX_RETRIES", 0)
    detail = " unsupported\n option " + ("x" * 400)
    _install_client(monkeypatch, _response({"error": detail}, status_code=400))

    with pytest.raises(OllamaHTTPError) as exc_info:
        OllamaTransport.get_tags()

    assert exc_info.value.status_code == 400
    assert exc_info.value.retryable is False
    assert exc_info.value.detail.startswith("unsupported option ")
    assert "\n" not in exc_info.value.detail
    assert len(exc_info.value.detail) == 300


def test_success_status_error_field_preserves_sanitized_detail(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_MAX_RETRIES", 0)
    _install_client(monkeypatch, _response({"error": " invalid\n schema "}))

    with pytest.raises(OllamaInvalidResponseError, match="Detail: invalid schema"):
        OllamaTransport.get_tags()


def test_schema_error_logs_locations_without_response_values(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_MAX_RETRIES", 0)
    _install_client(monkeypatch, _response({"models": "private-response-value"}))

    with pytest.raises(OllamaSchemaValidationError) as exc_info:
        OllamaTransport.get_tags()

    assert "models:list_type" in str(exc_info.value)
    assert "private-response-value" not in str(exc_info.value)


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


def test_embedding_throttle_logs_skipped_single_and_batch_requests(monkeypatch):
    warning = MagicMock()
    monkeypatch.setattr("app.services.embedding_service.logger.warning", warning)
    EmbeddingService._failed_models_cache["embedding-model"] = time.time()

    assert EmbeddingService._call_ollama_embed("embedding-model", "resume") is None
    assert EmbeddingService._call_ollama_batch_embed("embedding-model", ["resume"]) is None

    assert warning.call_count == 2
    assert all("RECENT_MODEL_FAILURE" in request.args[0] for request in warning.call_args_list)


def test_disabled_llm_returns_fallback_without_transport(monkeypatch):
    _disable_cache(monkeypatch)
    monkeypatch.setattr(settings, "LLM_ENABLED", False)
    execute = MagicMock(side_effect=AssertionError("transport must not run when LLM is disabled"))
    monkeypatch.setattr(OllamaTransport, "execute", execute)

    result = OllamaLLMService.call_qwen("analyze", "phase5", "disabled")

    assert result is None
    execute.assert_not_called()


@pytest.mark.asyncio
async def test_empty_work_experience_result_raises_typed_ollama_error(monkeypatch):
    execute = MagicMock(return_value=None)
    monkeypatch.setattr(OllamaLLMService, "_execute_structured_generation", execute)

    with pytest.raises(OllamaError, match="Failed to generate work experience extraction") as exc_info:
        await OllamaLLMService.extract_work_experience("extract employment", "1.0", "work-experience-cache")

    assert exc_info.value.operation == "work_experience_extraction"
    assert exc_info.value.retryable is True
    execute.assert_called_once()


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
                json={"models": [{"name": "llama3.2:3b"}]},
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
    assert all(result.value.models[0].name == "llama3.2:3b" for result in results)


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
