from __future__ import annotations
import json
import math
import os
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar

import httpx
from filelock import FileLock, Timeout as FileLockTimeout
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.config import settings
from app.core.logging import logger

T = TypeVar("T")


class OllamaError(RuntimeError):
    def __init__(self, message: str, *, operation: str, retryable: bool = True):
        super().__init__(message)
        self.operation = operation
        self.retryable = retryable


class OllamaUnavailableError(OllamaError):
    pass


class OllamaTimeoutError(OllamaError):
    pass


class OllamaConcurrencyError(OllamaTimeoutError):
    pass


class OllamaLiveAccessDisabledError(OllamaError):
    pass


class OllamaHTTPError(OllamaError):
    def __init__(self, message: str, *, operation: str, status_code: int, retryable: bool):
        super().__init__(message, operation=operation, retryable=retryable)
        self.status_code = status_code


class OllamaModelUnavailableError(OllamaHTTPError):
    def __init__(self, model: str, *, operation: str):
        super().__init__(
            f"Ollama model '{model}' is unavailable.",
            operation=operation,
            status_code=404,
            retryable=False,
        )
        self.model = model


class OllamaInvalidResponseError(OllamaError):
    pass


class OllamaSchemaValidationError(OllamaInvalidResponseError):
    pass


class OllamaGenerateEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    model: str
    response: str = ""
    thinking: str = ""
    done: bool
    done_reason: str
    total_duration: int = Field(default=0, ge=0)
    load_duration: int = Field(default=0, ge=0)
    prompt_eval_count: int = Field(default=0, ge=0)
    prompt_eval_duration: int = Field(default=0, ge=0)
    eval_count: int = Field(default=0, ge=0)
    eval_duration: int = Field(default=0, ge=0)

    @field_validator("model", "done_reason")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("Ollama generation fields must not be empty.")
        return value

    @field_validator("done_reason")
    @classmethod
    def validate_done_reason(cls, value: str) -> str:
        if value.lower() not in {"stop", "length", "load", "unload"}:
            raise ValueError("Ollama returned an unsupported completion reason.")
        return value

    @field_validator("done")
    @classmethod
    def validate_done(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Ollama generation did not complete.")
        return value


class OllamaUnloadEnvelope(OllamaGenerateEnvelope):
    @field_validator("done_reason")
    @classmethod
    def validate_unload_reason(cls, value: str) -> str:
        if value.lower() != "unload":
            raise ValueError("Ollama did not confirm model unload.")
        return value


class OllamaModelInfo(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value:
            raise ValueError("Ollama model name must not be empty.")
        return value


class OllamaTagsEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    models: list[OllamaModelInfo] = Field(default_factory=list)

    @field_validator("models")
    @classmethod
    def deduplicate_models(cls, models: list[OllamaModelInfo]) -> list[OllamaModelInfo]:
        unique: list[OllamaModelInfo] = []
        seen: set[str] = set()
        for model in models:
            if model.name not in seen:
                seen.add(model.name)
                unique.append(model)
        return unique


class OllamaEmbedEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    model: str
    embeddings: list[list[float]] = Field(default_factory=list)
    total_duration: int = Field(default=0, ge=0)
    load_duration: int = Field(default=0, ge=0)
    prompt_eval_count: int = Field(default=0, ge=0)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        if not value:
            raise ValueError("Ollama embedding model must not be empty.")
        return value


@dataclass(frozen=True)
class OllamaTransportResult(Generic[T]):
    value: T
    response_data: dict[str, Any]
    duration_ms: float
    attempts: int


class OllamaTransport:
    """Single serialized transport for all Ollama operations."""

    _client: httpx.Client | None = None
    _client_fingerprint: tuple[Any, ...] | None = None
    _client_lock = threading.RLock()
    _operation_lock = threading.RLock()
    _metrics_lock = threading.Lock()
    _metrics: dict[str, Any] = {
        "requests": 0,
        "successes": 0,
        "failures": 0,
        "retries": 0,
        "timeouts": 0,
        "unloads": 0,
        "unload_failures": 0,
        "response_bytes": 0,
        "lock_wait_ms": 0.0,
        "model_load_duration_ms": 0.0,
        "model_inference_duration_ms": 0.0,
        "unload_duration_ms": 0.0,
        "total_duration_ms": 0.0,
        "operations": {},
    }

    @classmethod
    def get_client(cls) -> httpx.Client:
        if os.environ.get("PYTEST_CURRENT_TEST") and not settings.OLLAMA_LIVE_TESTS_ENABLED:
            raise OllamaLiveAccessDisabledError(
                "Live Ollama access is disabled during tests.",
                operation="client",
                retryable=False,
            )

        fingerprint = (
            settings.OLLAMA_BASE_URL.rstrip("/"),
            settings.OLLAMA_REQUEST_TIMEOUT,
            settings.OLLAMA_CONNECT_TIMEOUT_SECONDS,
            settings.OLLAMA_MAX_CONNECTIONS,
            settings.OLLAMA_MAX_KEEPALIVE_CONNECTIONS,
        )
        with cls._client_lock:
            if cls._client is None or cls._client.is_closed or cls._client_fingerprint != fingerprint:
                if cls._client is not None and not cls._client.is_closed:
                    cls._client.close()
                cls._client = httpx.Client(
                    base_url=fingerprint[0],
                    timeout=httpx.Timeout(
                        settings.OLLAMA_REQUEST_TIMEOUT,
                        connect=settings.OLLAMA_CONNECT_TIMEOUT_SECONDS,
                    ),
                    limits=httpx.Limits(
                        max_connections=max(1, settings.OLLAMA_MAX_CONNECTIONS),
                        max_keepalive_connections=max(1, settings.OLLAMA_MAX_KEEPALIVE_CONNECTIONS),
                    ),
                )
                cls._client_fingerprint = fingerprint
            return cls._client

    @classmethod
    def close(cls) -> None:
        with cls._client_lock:
            if cls._client is not None and not cls._client.is_closed:
                cls._client.close()
            cls._client = None
            cls._client_fingerprint = None

    @classmethod
    @contextmanager
    def _operation_scope(cls, operation: str, models: tuple[str, ...] = ()) -> Iterator[None]:
        started = time.perf_counter()
        lock_timeout = max(0.0, settings.OLLAMA_LOCK_TIMEOUT_SECONDS)
        acquired = cls._operation_lock.acquire(timeout=lock_timeout)
        if not acquired:
            raise OllamaConcurrencyError(
                "Timed out waiting for the local Ollama operation lock.",
                operation=operation,
            )

        file_lock: FileLock | None = None
        try:
            lock_path = Path(settings.OLLAMA_LOCK_FILE)
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            file_lock = FileLock(str(lock_path), timeout=lock_timeout)
            file_lock.acquire()
            lock_wait_ms = round((time.perf_counter() - started) * 1000.0, 2)
            cls._record_lock_wait(lock_wait_ms)
            logger.info(f"[OLLAMA] operation={operation} status=LOCKED wait_ms={lock_wait_ms}")
            yield
        except FileLockTimeout as exc:
            raise OllamaConcurrencyError(
                "Timed out waiting for the shared Ollama operation lock.",
                operation=operation,
            ) from exc
        finally:
            try:
                if file_lock is not None and file_lock.is_locked:
                    file_lock.release()
            finally:
                try:
                    cls.close()
                finally:
                    cls._operation_lock.release()

    @classmethod
    def execute(
        cls,
        *,
        operation: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        parser: Callable[[dict[str, Any]], T],
    ) -> OllamaTransportResult[T]:
        """Compatibility entry point for one non-model or explicitly managed request."""
        model = str((payload or {}).get("model") or "").strip()
        with cls._operation_scope(operation, (model,) if model else ()):
            try:
                return cls._execute_request(
                    operation=operation,
                    method=method,
                    path=path,
                    payload=payload,
                    parser=parser,
                )
            finally:
                if model and operation != "unload":
                    cls._unload_safely(model, parent_operation=operation)

    @classmethod
    def _execute_request(
        cls,
        *,
        operation: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        parser: Callable[[dict[str, Any]], T],
        max_retries: int | None = None,
        deadline: float | None = None,
    ) -> OllamaTransportResult[T]:
        retries = max(0, settings.OLLAMA_MAX_RETRIES if max_retries is None else max_retries)
        total_attempts = retries + 1
        timeout_seconds = cls._operation_timeout(operation)
        started = time.perf_counter()
        operation_deadline = deadline if deadline is not None else started + timeout_seconds
        last_error: OllamaError | None = None

        for attempt in range(1, total_attempts + 1):
            remaining = operation_deadline - time.perf_counter()
            if remaining <= 0:
                cls._record_timeout()
                last_error = OllamaTimeoutError(
                    "Ollama operation exceeded its total deadline.",
                    operation=operation,
                )
                break

            cls._record_attempt(operation)
            logger.info(f"[OLLAMA] operation={operation} attempt={attempt}/{total_attempts} status=START")
            try:
                response_data, response_bytes = cls._request_json(
                    operation=operation,
                    method=method,
                    path=path,
                    payload=payload,
                    timeout_seconds=remaining,
                )
                cls._validate_error_field(response_data, operation=operation)
                value = parser(response_data)
                duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
                cls._record_success(operation, duration_ms, response_bytes, response_data)
                logger.info(
                    f"[OLLAMA] operation={operation} attempt={attempt}/{total_attempts} status=SUCCESS "
                    f"duration_ms={duration_ms} response_bytes={response_bytes}"
                )
                return OllamaTransportResult(
                    value=value,
                    response_data=response_data,
                    duration_ms=duration_ms,
                    attempts=attempt,
                )
            except OllamaError as exc:
                last_error = exc
            except httpx.TimeoutException as exc:
                cls._record_timeout()
                last_error = OllamaTimeoutError("Ollama request timed out.", operation=operation)
                last_error.__cause__ = exc
            except (httpx.ConnectError, httpx.NetworkError, httpx.RequestError) as exc:
                last_error = OllamaUnavailableError("Ollama is unavailable.", operation=operation)
                last_error.__cause__ = exc
            except json.JSONDecodeError as exc:
                last_error = OllamaInvalidResponseError("Ollama returned invalid JSON.", operation=operation)
                last_error.__cause__ = exc
            except ValidationError as exc:
                last_error = OllamaSchemaValidationError("Ollama response failed schema validation.", operation=operation)
                last_error.__cause__ = exc
            except (TypeError, ValueError) as exc:
                last_error = OllamaInvalidResponseError("Ollama response could not be normalized.", operation=operation)
                last_error.__cause__ = exc

            assert last_error is not None
            should_retry = last_error.retryable and attempt <= retries
            logger.warning(
                f"[OLLAMA] operation={operation} attempt={attempt}/{total_attempts} "
                f"status={'RETRY' if should_retry else 'FAILED'} error={type(last_error).__name__}"
            )
            if not should_retry:
                break
            cls._record_retry()
            backoff = max(0.0, settings.OLLAMA_RETRY_BACKOFF_SECONDS) * (2 ** (attempt - 1))
            remaining = operation_deadline - time.perf_counter()
            if backoff <= 0:
                continue
            if backoff >= remaining:
                cls._record_timeout()
                last_error = OllamaTimeoutError(
                    "Ollama retry backoff exceeded the total deadline.",
                    operation=operation,
                )
                break
            time.sleep(backoff)

        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        cls._record_failure(operation, duration_ms)
        if last_error is None:
            last_error = OllamaUnavailableError("Ollama request failed.", operation=operation)
        logger.error(f"[OLLAMA] operation={operation} status=FAILED duration_ms={duration_ms} error={type(last_error).__name__}")
        raise last_error

    @classmethod
    def _request_json(
        cls,
        *,
        operation: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        timeout_seconds: float,
    ) -> tuple[dict[str, Any], int]:
        request_kwargs: dict[str, Any] = {
            "timeout": httpx.Timeout(
                max(0.001, timeout_seconds),
                connect=min(max(0.001, timeout_seconds), settings.OLLAMA_CONNECT_TIMEOUT_SECONDS),
            )
        }
        if payload is not None:
            request_kwargs["json"] = payload

        max_bytes = max(1, settings.OLLAMA_MAX_RESPONSE_BYTES)
        with cls.get_client().stream(method, path, **request_kwargs) as response:
            cls._raise_for_status(response, operation=operation, payload=payload)
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > max_bytes:
                raise OllamaInvalidResponseError(
                    "Ollama response exceeded the configured size limit.",
                    operation=operation,
                    retryable=False,
                )

            chunks: list[bytes] = []
            response_bytes = 0
            for chunk in response.iter_bytes():
                response_bytes += len(chunk)
                if response_bytes > max_bytes:
                    raise OllamaInvalidResponseError(
                        "Ollama response exceeded the configured size limit.",
                        operation=operation,
                        retryable=False,
                    )
                chunks.append(chunk)

        response_data = json.loads(b"".join(chunks))
        if not isinstance(response_data, dict):
            raise OllamaInvalidResponseError(
                "Ollama response must be a JSON object.",
                operation=operation,
            )
        return response_data, response_bytes

    @classmethod
    def get_tags(cls) -> OllamaTransportResult[OllamaTagsEnvelope]:
        return cls.execute(
            operation="tags",
            method="GET",
            path="/api/tags",
            parser=OllamaTagsEnvelope.model_validate,
        )

    @classmethod
    def generate(
        cls,
        *,
        operation: str,
        payload: dict[str, Any],
        parser: Callable[[dict[str, Any]], T],
    ) -> OllamaTransportResult[T]:
        model = cls._require_requested_model(payload, operation=operation)

        def validated_parser(data: dict[str, Any]) -> T:
            envelope = OllamaGenerateEnvelope.model_validate(data)
            cls._validate_returned_model(model, envelope.model, operation=operation)
            return parser(data)

        with cls._operation_scope(operation, (model,)):
            try:
                return cls._execute_request(
                    operation=operation,
                    method="POST",
                    path="/api/generate",
                    payload=payload,
                    parser=validated_parser,
                )
            finally:
                cls._unload_safely(model, parent_operation=operation)

    @classmethod
    def embed(cls, model: str, inputs: list[str]) -> OllamaTransportResult[list[list[float]]]:
        normalized_model = model.strip()
        if not normalized_model:
            raise OllamaInvalidResponseError("An embedding model is required.", operation="embed", retryable=False)
        if not inputs or any(not isinstance(value, str) or not value.strip() for value in inputs):
            raise OllamaInvalidResponseError("Embedding inputs must be non-empty strings.", operation="embed", retryable=False)

        unique_inputs: list[str] = []
        unique_indexes: dict[str, int] = {}
        restore_indexes: list[int] = []
        for value in inputs:
            if value not in unique_indexes:
                unique_indexes[value] = len(unique_inputs)
                unique_inputs.append(value)
            restore_indexes.append(unique_indexes[value])

        batch_size = max(1, settings.OLLAMA_EMBED_BATCH_SIZE)
        all_embeddings: list[list[float]] = []
        response_data: dict[str, Any] = {"model": normalized_model, "embeddings": []}
        duration_ms = 0.0
        attempts = 0
        deadline = time.perf_counter() + cls._operation_timeout("embed")

        with cls._operation_scope("embed", (normalized_model,)):
            try:
                for offset in range(0, len(unique_inputs), batch_size):
                    batch = unique_inputs[offset : offset + batch_size]
                    result = cls._embed_batch_with_split(normalized_model, batch, deadline=deadline)
                    all_embeddings.extend(result.value)
                    duration_ms += result.duration_ms
                    attempts += result.attempts
                restored = [all_embeddings[index] for index in restore_indexes]
                response_data["embeddings"] = restored
                return OllamaTransportResult(
                    value=restored,
                    response_data=response_data,
                    duration_ms=round(duration_ms, 2),
                    attempts=attempts,
                )
            finally:
                cls._unload_safely(normalized_model, parent_operation="embed")

    @classmethod
    def _embed_batch_with_split(cls, model: str, inputs: list[str], *, deadline: float) -> OllamaTransportResult[list[list[float]]]:
        try:
            return cls._execute_embedding_batch(model, inputs, deadline=deadline)
        except OllamaSchemaValidationError as exc:
            if not exc.retryable:
                raise
            minimum = max(2, settings.OLLAMA_EMBED_MIN_SPLIT_SIZE)
            if len(inputs) <= minimum:
                raise
            midpoint = len(inputs) // 2
            left = cls._embed_batch_with_split(model, inputs[:midpoint], deadline=deadline)
            right = cls._embed_batch_with_split(model, inputs[midpoint:], deadline=deadline)
            values = left.value + right.value
            return OllamaTransportResult(
                value=values,
                response_data={"model": model, "embeddings": values},
                duration_ms=round(left.duration_ms + right.duration_ms, 2),
                attempts=left.attempts + right.attempts,
            )

    @classmethod
    def _execute_embedding_batch(cls, model: str, inputs: list[str], *, deadline: float) -> OllamaTransportResult[list[list[float]]]:
        payload = cls.build_embedding_payload(model=model, inputs=inputs)

        def parse(data: dict[str, Any]) -> list[list[float]]:
            envelope = OllamaEmbedEnvelope.model_validate(data)
            cls._validate_returned_model(model, envelope.model, operation="embed")
            cls._validate_embeddings(envelope.embeddings, expected_count=len(inputs))
            return [[float(value) for value in vector] for vector in envelope.embeddings]

        return cls._execute_request(
            operation="embed",
            method="POST",
            path="/api/embed",
            payload=payload,
            parser=parse,
            deadline=deadline,
        )

    @classmethod
    def unload(cls, model: str) -> OllamaTransportResult[bool]:
        normalized_model = model.strip()
        if not normalized_model:
            raise OllamaInvalidResponseError("An Ollama model is required for unload.", operation="unload", retryable=False)
        with cls._operation_scope("unload"):
            try:
                result = cls._unload_request(normalized_model)
                with cls._metrics_lock:
                    cls._metrics["unloads"] += 1
                return result
            except OllamaError:
                with cls._metrics_lock:
                    cls._metrics["unload_failures"] += 1
                raise

    @classmethod
    def _unload_request(cls, model: str) -> OllamaTransportResult[bool]:
        def parse(data: dict[str, Any]) -> bool:
            envelope = OllamaUnloadEnvelope.model_validate(data)
            cls._validate_returned_model(model, envelope.model, operation="unload")
            return True

        return cls._execute_request(
            operation="unload",
            method="POST",
            path="/api/generate",
            payload=cls.build_unload_payload(model),
            parser=parse,
            max_retries=0,
        )

    @classmethod
    def _unload_safely(cls, model: str, *, parent_operation: str) -> None:
        try:
            cls._unload_request(model)
            with cls._metrics_lock:
                cls._metrics["unloads"] += 1
            logger.info(f"[OLLAMA] operation={parent_operation} model='{model}' status=UNLOADED")
        except OllamaError as exc:
            with cls._metrics_lock:
                cls._metrics["unload_failures"] += 1
            logger.warning(
                f"[OLLAMA] operation={parent_operation} model='{model}' status=UNLOAD_FAILED error={type(exc).__name__}"
            )

    @staticmethod
    def build_generation_payload(
        *,
        model: str,
        prompt: str,
        response_schema: dict[str, Any],
        think: bool,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "model": model,
            "prompt": prompt,
            "format": response_schema,
            "stream": False,
            "think": think,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
            "options": options,
        }

    @staticmethod
    def build_embedding_payload(*, model: str, inputs: list[str]) -> dict[str, Any]:
        return {
            "model": model,
            "input": inputs,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
        }

    @staticmethod
    def build_unload_payload(model: str) -> dict[str, Any]:
        return {"model": model, "keep_alive": 0}

    @staticmethod
    def extract_json(text: str, *, operation: str) -> Any:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            first_newline = cleaned.find("\n")
            cleaned = cleaned[first_newline + 1 :] if first_newline >= 0 else cleaned[3:]
            cleaned = cleaned.removesuffix("```")
            cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as original_error:
            decoder = json.JSONDecoder()
            for index, character in enumerate(cleaned):
                if character not in "[{":
                    continue
                try:
                    value, _ = decoder.raw_decode(cleaned[index:])
                    return value
                except json.JSONDecodeError:
                    continue
            raise OllamaInvalidResponseError(
                "Ollama generation did not contain valid structured JSON.",
                operation=operation,
            ) from original_error

    @classmethod
    def get_metrics(cls) -> dict[str, Any]:
        with cls._metrics_lock:
            metrics = {key: value for key, value in cls._metrics.items() if key != "operations"}
            metrics["operations"] = {operation: operation_metrics.copy() for operation, operation_metrics in cls._metrics["operations"].items()}
            completed = int(metrics["successes"]) + int(metrics["failures"])
            metrics["average_duration_ms"] = round(float(metrics["total_duration_ms"]) / completed, 2) if completed else 0.0
            return metrics

    @classmethod
    def reset_metrics(cls) -> None:
        with cls._metrics_lock:
            cls._metrics = {
                "requests": 0,
                "successes": 0,
                "failures": 0,
                "retries": 0,
                "timeouts": 0,
                "unloads": 0,
                "unload_failures": 0,
                "response_bytes": 0,
                "lock_wait_ms": 0.0,
                "model_load_duration_ms": 0.0,
                "model_inference_duration_ms": 0.0,
                "unload_duration_ms": 0.0,
                "total_duration_ms": 0.0,
                "operations": {},
            }

    @classmethod
    def _operation_timeout(cls, operation: str) -> float:
        if operation == "tags":
            return max(0.001, settings.OLLAMA_TAGS_TIMEOUT_SECONDS)
        if operation == "embed":
            return max(0.001, settings.OLLAMA_EMBED_TIMEOUT_SECONDS)
        if operation == "unload":
            return max(0.001, settings.OLLAMA_UNLOAD_TIMEOUT_SECONDS)
        return max(0.001, settings.OLLAMA_GENERATE_TIMEOUT_SECONDS)

    @staticmethod
    def _require_requested_model(payload: dict[str, Any], *, operation: str) -> str:
        model = str(payload.get("model") or "").strip()
        if not model:
            raise OllamaInvalidResponseError("An Ollama model is required.", operation=operation, retryable=False)
        return model

    @staticmethod
    def _validate_error_field(data: dict[str, Any], *, operation: str) -> None:
        if data.get("error"):
            raise OllamaInvalidResponseError("Ollama returned an error response.", operation=operation, retryable=False)

    @staticmethod
    def _validate_returned_model(requested: str, returned: str, *, operation: str) -> None:
        requested_name = requested.strip()
        returned_name = returned.strip()
        requested_canonical = requested_name.removesuffix(":latest")
        returned_canonical = returned_name.removesuffix(":latest")
        if not returned_name or returned_canonical != requested_canonical:
            raise OllamaSchemaValidationError(
                "Ollama returned a response for a different model.",
                operation=operation,
                retryable=False,
            )

    @classmethod
    def _validate_embeddings(cls, embeddings: list[list[float]], *, expected_count: int) -> None:
        if len(embeddings) != expected_count or not embeddings:
            raise OllamaSchemaValidationError(
                "Ollama embedding count does not match the input count.",
                operation="embed",
            )

        dimensions = {len(vector) for vector in embeddings}
        if len(dimensions) != 1 or 0 in dimensions:
            raise OllamaSchemaValidationError("Ollama embedding dimensions are inconsistent.", operation="embed")
        dimension = next(iter(dimensions))
        expected_dimension = max(0, settings.OLLAMA_EMBEDDING_EXPECTED_DIMENSION)
        if dimension > max(1, settings.OLLAMA_EMBEDDING_MAX_DIMENSION):
            raise OllamaSchemaValidationError("Ollama embedding dimension exceeds the configured maximum.", operation="embed", retryable=False)
        if expected_dimension and dimension != expected_dimension:
            raise OllamaSchemaValidationError("Ollama embedding dimension does not match the configured model contract.", operation="embed", retryable=False)

        for vector in embeddings:
            if any(not math.isfinite(float(value)) for value in vector):
                raise OllamaSchemaValidationError("Ollama embedding contains a non-finite value.", operation="embed", retryable=False)
            if not any(float(value) != 0.0 for value in vector):
                raise OllamaSchemaValidationError("Ollama embedding must not be a zero vector.", operation="embed", retryable=False)

    @classmethod
    def _raise_for_status(
        cls,
        response: httpx.Response,
        *,
        operation: str,
        payload: dict[str, Any] | None,
    ) -> None:
        if response.status_code < 400:
            return
        model = str((payload or {}).get("model") or "")
        if response.status_code == 404 and model:
            raise OllamaModelUnavailableError(model, operation=operation)
        retryable = response.status_code in (408, 429) or response.status_code >= 500
        raise OllamaHTTPError(
            f"Ollama returned HTTP {response.status_code}.",
            operation=operation,
            status_code=response.status_code,
            retryable=retryable,
        )

    @classmethod
    def _record_attempt(cls, operation: str) -> None:
        with cls._metrics_lock:
            cls._metrics["requests"] += 1
            operations = cls._metrics["operations"]
            operation_metrics = operations.setdefault(operation, {"requests": 0, "successes": 0, "failures": 0})
            operation_metrics["requests"] += 1

    @classmethod
    def _record_success(cls, operation: str, duration_ms: float, response_bytes: int, response_data: dict[str, Any]) -> None:
        with cls._metrics_lock:
            cls._metrics["successes"] += 1
            cls._metrics["response_bytes"] += response_bytes
            cls._metrics["total_duration_ms"] += duration_ms
            cls._metrics["model_load_duration_ms"] += max(0, int(response_data.get("load_duration") or 0)) / 1_000_000.0
            cls._metrics["model_inference_duration_ms"] += max(0, int(response_data.get("eval_duration") or 0)) / 1_000_000.0
            if operation == "unload":
                cls._metrics["unload_duration_ms"] += duration_ms
            cls._metrics["operations"][operation]["successes"] += 1

    @classmethod
    def _record_failure(cls, operation: str, duration_ms: float) -> None:
        with cls._metrics_lock:
            cls._metrics["failures"] += 1
            cls._metrics["total_duration_ms"] += duration_ms
            cls._metrics["operations"].setdefault(operation, {"requests": 0, "successes": 0, "failures": 0})["failures"] += 1

    @classmethod
    def _record_retry(cls) -> None:
        with cls._metrics_lock:
            cls._metrics["retries"] += 1

    @classmethod
    def _record_timeout(cls) -> None:
        with cls._metrics_lock:
            cls._metrics["timeouts"] += 1

    @classmethod
    def _record_lock_wait(cls, duration_ms: float) -> None:
        with cls._metrics_lock:
            cls._metrics["lock_wait_ms"] += duration_ms
