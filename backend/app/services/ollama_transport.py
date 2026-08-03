import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

import httpx
from pydantic import BaseModel, Field, ValidationError

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
    response: str = ""
    thinking: str = ""
    eval_count: int = 0
    eval_duration: int = 0


class OllamaModelInfo(BaseModel):
    name: str


class OllamaTagsEnvelope(BaseModel):
    models: list[OllamaModelInfo] = Field(default_factory=list)


class OllamaEmbedEnvelope(BaseModel):
    embeddings: list[list[float]] = Field(default_factory=list)


@dataclass(frozen=True)
class OllamaTransportResult(Generic[T]):
    value: T
    response_data: dict[str, Any]
    duration_ms: float
    attempts: int


class OllamaTransport:
    """One pooled, version-stable transport for every Ollama HTTP operation."""

    _client: httpx.Client | None = None
    _client_fingerprint: tuple[Any, ...] | None = None
    _client_lock = threading.RLock()
    _metrics_lock = threading.Lock()
    _metrics: dict[str, Any] = {
        "requests": 0,
        "successes": 0,
        "failures": 0,
        "retries": 0,
        "timeouts": 0,
        "total_duration_ms": 0.0,
        "operations": {},
    }

    @classmethod
    def get_client(cls) -> httpx.Client:
        fingerprint = (
            settings.OLLAMA_BASE_URL.rstrip("/"),
            settings.OLLAMA_REQUEST_TIMEOUT,
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
                        connect=settings.OLLAMA_REQUEST_TIMEOUT,
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
    def execute(
        cls,
        *,
        operation: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        parser: Callable[[dict[str, Any]], T],
    ) -> OllamaTransportResult[T]:
        max_retries = max(0, settings.OLLAMA_MAX_RETRIES)
        total_attempts = max_retries + 1
        started = time.perf_counter()
        last_error: OllamaError | None = None

        for attempt in range(1, total_attempts + 1):
            cls._record_attempt(operation)
            logger.info(f"[OLLAMA] operation={operation} attempt={attempt}/{total_attempts} status=START")
            try:
                request_kwargs = {"json": payload} if payload is not None else {}
                response = cls.get_client().request(method, path, **request_kwargs)
                cls._raise_for_status(response, operation=operation, payload=payload)
                response_data = response.json()
                if not isinstance(response_data, dict):
                    raise OllamaInvalidResponseError(
                        "Ollama response must be a JSON object.",
                        operation=operation,
                    )
                value = parser(response_data)
                duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
                cls._record_success(operation, duration_ms)
                logger.info(f"[OLLAMA] operation={operation} attempt={attempt}/{total_attempts} status=SUCCESS duration_ms={duration_ms}")
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
                last_error = OllamaTimeoutError(
                    "Ollama request timed out.",
                    operation=operation,
                )
                last_error.__cause__ = exc
            except (httpx.ConnectError, httpx.NetworkError, httpx.RequestError) as exc:
                last_error = OllamaUnavailableError(
                    "Ollama is unavailable.",
                    operation=operation,
                )
                last_error.__cause__ = exc
            except json.JSONDecodeError as exc:
                last_error = OllamaInvalidResponseError(
                    "Ollama returned invalid JSON.",
                    operation=operation,
                )
                last_error.__cause__ = exc
            except ValidationError as exc:
                last_error = OllamaSchemaValidationError(
                    "Ollama response failed schema validation.",
                    operation=operation,
                )
                last_error.__cause__ = exc
            except (TypeError, ValueError) as exc:
                last_error = OllamaInvalidResponseError(
                    "Ollama response could not be normalized.",
                    operation=operation,
                )
                last_error.__cause__ = exc

            assert last_error is not None
            should_retry = last_error.retryable and attempt <= max_retries
            logger.warning(f"[OLLAMA] operation={operation} attempt={attempt}/{total_attempts} status={'RETRY' if should_retry else 'FAILED'} error={type(last_error).__name__}")
            if not should_retry:
                break
            cls._record_retry()
            backoff = max(0.0, settings.OLLAMA_RETRY_BACKOFF_SECONDS) * (2 ** (attempt - 1))
            if backoff:
                time.sleep(backoff)

        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        cls._record_failure(operation, duration_ms)
        if last_error is None:
            last_error = OllamaUnavailableError("Ollama request failed.", operation=operation)
        logger.error(f"[OLLAMA] operation={operation} status=FAILED duration_ms={duration_ms} error={type(last_error).__name__}")
        raise last_error

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
        return cls.execute(
            operation=operation,
            method="POST",
            path="/api/generate",
            payload=payload,
            parser=parser,
        )

    @classmethod
    def embed(cls, model: str, inputs: list[str]) -> OllamaTransportResult[list[list[float]]]:
        payload = cls.build_embedding_payload(model=model, inputs=inputs)

        def parse(data: dict[str, Any]) -> list[list[float]]:
            envelope = OllamaEmbedEnvelope.model_validate(data)
            if len(envelope.embeddings) != len(inputs) or any(not vector for vector in envelope.embeddings):
                raise OllamaSchemaValidationError(
                    "Ollama embedding count does not match the input count.",
                    operation="embed",
                )
            return envelope.embeddings

        return cls.execute(
            operation="embed",
            method="POST",
            path="/api/embed",
            payload=payload,
            parser=parse,
        )

    @classmethod
    def unload(cls, model: str) -> OllamaTransportResult[bool]:
        return cls.generate(
            operation="unload",
            payload=cls.build_unload_payload(model),
            parser=lambda _data: True,
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
                "total_duration_ms": 0.0,
                "operations": {},
            }

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
    def _record_success(cls, operation: str, duration_ms: float) -> None:
        with cls._metrics_lock:
            cls._metrics["successes"] += 1
            cls._metrics["total_duration_ms"] += duration_ms
            cls._metrics["operations"][operation]["successes"] += 1

    @classmethod
    def _record_failure(cls, operation: str, duration_ms: float) -> None:
        with cls._metrics_lock:
            cls._metrics["failures"] += 1
            cls._metrics["total_duration_ms"] += duration_ms
            cls._metrics["operations"][operation]["failures"] += 1

    @classmethod
    def _record_retry(cls) -> None:
        with cls._metrics_lock:
            cls._metrics["retries"] += 1

    @classmethod
    def _record_timeout(cls) -> None:
        with cls._metrics_lock:
            cls._metrics["timeouts"] += 1
