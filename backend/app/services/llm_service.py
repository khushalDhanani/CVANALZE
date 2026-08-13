from __future__ import annotations
import hashlib
import time
from dataclasses import dataclass
from typing import Any, TypeVar, cast

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.logging import logger
from app.core.metrics import _metrics
from app.core.profiler import PipelineProfiler
from app.core.request_context import get_request_context_ids
from app.repositories.llm_cache import LLMCacheEntry, LLMCacheRepository
from app.repositories.llm_trace import LLMTraceRepository
from app.schemas.analysis import (
    DynamicMappingResponse,
    OptimizedLLMMatchResponse,
    QwenCVAnalysis,
)
from app.schemas.profile import DynamicCandidateProfile
from app.schemas.work_experience_llm import LLMWorkExperienceExtraction
from app.services.ollama_transport import (
    OllamaError,
    OllamaGenerateEnvelope,
    OllamaInvalidResponseError,
    OllamaTransport,
)
from app.schemas.llm_trace import LLMExecutionTrace

TModel = TypeVar("TModel", bound=BaseModel)


def _get_httpx_client(timeout: float | None = None) -> httpx.Client:
    """Compatibility alias for callers that previously accessed the pooled client helper."""
    del timeout
    return OllamaTransport.get_client()


@dataclass(frozen=True)
class _StructuredGeneration:
    validated: BaseModel
    structured_data: dict[str, Any]
    raw_response: str
    reasoning: str
    envelope: OllamaGenerateEnvelope
    validation_ms: float


class OllamaLLMService:
    _model_digests: dict[str, str] = {}
    _thinking_model_families = frozenset({"deepseek-r1", "gpt-oss", "qwen3", "qwen3.5"})

    @staticmethod
    def _model_identifier_hash(model: str) -> str:
        return hashlib.sha256(model.strip().encode("utf-8")).hexdigest()

    @classmethod
    def _supports_thinking(cls, model: str) -> bool:
        model_family = model.strip().lower().split(":", 1)[0].rsplit("/", 1)[-1]
        return model_family in cls._thinking_model_families

    @staticmethod
    def _remove_legacy_thinking_directive(prompt: str) -> tuple[str, bool]:
        lines = prompt.splitlines()
        if lines and lines[0].strip().lower() in {"/think", "/no_think"}:
            return "\n".join(lines[1:]).lstrip(), True
        return prompt, False

    @classmethod
    def _trace(
        cls,
        *,
        operation: str,
        model: str,
        prompt_version: str,
        prompt_hash: str,
        source_hash: str,
        cache_status: str,
        validation_status: str,
        fallback_used: bool,
        duration_ms: float = 0.0,
        inference_ms: float = 0.0,
        validation_ms: float = 0.0,
        attempts: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        completion_reason: str = "",
        error_class: str = "",
        quality_metadata: dict[str, Any] | None = None,
    ) -> None:
        request_id, correlation_id = get_request_context_ids()
        normalized_source_hash = source_hash if len(source_hash) <= 64 else hashlib.sha256(source_hash.encode("utf-8")).hexdigest()
        LLMTraceRepository.save(
            LLMExecutionTrace(
                request_id=request_id,
                correlation_id=correlation_id,
                operation=operation,
                model_identifier_hash=cls._model_identifier_hash(model),
                model_digest=cls._model_digests.get(model, ""),
                prompt_version=prompt_version,
                prompt_hash=prompt_hash,
                source_hash=normalized_source_hash,
                source_freshness="versioned" if normalized_source_hash else "unknown",
                cache_status=cache_status,
                validation_status=validation_status,
                fallback_used=fallback_used,
                duration_ms=duration_ms,
                inference_ms=inference_ms,
                validation_ms=validation_ms,
                attempts=attempts,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                completion_reason=completion_reason,
                error_class=error_class,
                quality_metadata=quality_metadata or {},
            )
        )

    @classmethod
    def get_status(cls) -> tuple[bool, list[str]]:
        """Return Ollama reachability and normalized models from one tags request."""
        try:
            result = OllamaTransport.get_tags()
            cls._model_digests = {model.name: model.digest for model in result.value.models if model.digest}
            return True, [model.name for model in result.value.models]
        except OllamaError as exc:
            logger.warning(f"[OLLAMA] operation=tags status=FALLBACK error={type(exc).__name__}")
            return False, []

    @classmethod
    def record_quality_trace(
        cls,
        *,
        operation: str,
        prompt: str,
        prompt_version: str,
        source_hash: str,
        quality_metadata: dict[str, Any],
    ) -> None:
        cls._trace(
            operation=operation,
            model=settings.OLLAMA_MODEL,
            prompt_version=prompt_version,
            prompt_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            source_hash=source_hash,
            cache_status="BYPASS",
            validation_status="VALID",
            fallback_used=False,
            quality_metadata=quality_metadata,
        )

    @classmethod
    def check_health(cls) -> bool:
        healthy, _ = cls.get_status()
        return healthy

    @classmethod
    def get_available_models(cls) -> list[str]:
        _, models = cls.get_status()
        return models

    @classmethod
    def extract_candidate_profile(
        cls,
        prompt: str,
        prompt_version: str,
        cache_key: str = "",
    ) -> DynamicCandidateProfile | None:
        return cls._execute_structured_generation(
            operation="profile_extraction",
            prompt=prompt,
            prompt_version=prompt_version,
            cache_key=cache_key,
            response_model=DynamicCandidateProfile,
            think=False,
            options={
                "num_predict": settings.OLLAMA_GENERATION_NUM_PREDICT,
                "num_ctx": settings.OLLAMA_GENERATION_NUM_CTX,
                "temperature": 0.0,
            },
        )

    @classmethod
    def call_qwen(
        cls,
        prompt: str,
        prompt_version: str,
        cache_key: str = "",
    ) -> QwenCVAnalysis | None:
        return cls._execute_structured_generation(
            operation="qwen_analysis",
            prompt=prompt,
            prompt_version=prompt_version,
            cache_key=cache_key,
            response_model=QwenCVAnalysis,
            think=True,
            options={
                "num_predict": settings.OLLAMA_GENERATION_NUM_PREDICT,
                "num_ctx": settings.OLLAMA_GENERATION_NUM_CTX,
                "temperature": 0.0,
            },
        )

    @classmethod
    def call_qwen_dynamic(
        cls,
        prompt: str,
        prompt_version: str,
        cache_key: str = "",
    ) -> DynamicMappingResponse | None:
        return cls._execute_structured_generation(
            operation="dynamic_mapping",
            prompt=prompt,
            prompt_version=prompt_version,
            cache_key=cache_key,
            response_model=DynamicMappingResponse,
            think=True,
            options={
                "num_predict": settings.OLLAMA_GENERATION_NUM_PREDICT,
                "num_ctx": settings.OLLAMA_GENERATION_NUM_CTX,
                "temperature": 0.0,
            },
        )

    @classmethod
    def run_optimized_match(
        cls,
        prompt: str,
        prompt_version: str,
        cache_key: str,
        profiler: PipelineProfiler | None = None,
    ) -> OptimizedLLMMatchResponse | None:
        return cls._execute_structured_generation(
            operation="optimized_match",
            prompt=prompt,
            prompt_version=prompt_version,
            cache_key=cache_key,
            response_model=OptimizedLLMMatchResponse,
            think=True,
            options={
                "num_predict": settings.OLLAMA_OPTIMIZED_NUM_PREDICT,
                "num_ctx": settings.OLLAMA_GENERATION_NUM_CTX,
                "temperature": 0.0,
                "top_p": 0.9,
            },
            profiler=profiler,
        )

    @classmethod
    async def extract_work_experience(
        cls,
        prompt: str,
        prompt_version: str,
        cache_key: str,
    ) -> LLMWorkExperienceExtraction:
        import asyncio
        result = await asyncio.to_thread(
            cls._execute_structured_generation,
            operation="work_experience_extraction",
            prompt=prompt,
            prompt_version=prompt_version,
            cache_key=cache_key,
            response_model=LLMWorkExperienceExtraction,
            think=False,
            options={
                "num_predict": settings.OLLAMA_GENERATION_NUM_PREDICT,
                "num_ctx": settings.OLLAMA_GENERATION_NUM_CTX,
                "temperature": 0.0,
            },
        )
        if result is None:
            raise OllamaError("Failed to generate work experience extraction")
        return result

    @classmethod
    def generate_structured_json(
        cls,
        *,
        operation: str,
        prompt: str,
        prompt_version: str,
        cache_key: str,
        response_model: type[TModel],
        think: bool = False,
        options: dict[str, Any] | None = None,
        profiler: PipelineProfiler | None = None,
    ) -> TModel | None:
        """
        Public contract for calling Ollama with a structured JSON response schema.
        Handles caching, retries, parsing, and telemetry.
        """
        if options is None:
            options = {"temperature": 0.0}
        return cls._execute_structured_generation(
            operation=operation,
            prompt=prompt,
            prompt_version=prompt_version,
            cache_key=cache_key,
            response_model=response_model,
            think=think,
            options=options,
            profiler=profiler,
        )

    @classmethod
    def _execute_structured_generation(
        cls,
        *,
        operation: str,
        prompt: str,
        prompt_version: str,
        cache_key: str,
        response_model: type[TModel],
        think: bool,
        options: dict[str, Any],
        profiler: PipelineProfiler | None = None,
    ) -> TModel | None:
        model = settings.OLLAMA_MODEL
        request_prompt, removed_legacy_directive = cls._remove_legacy_thinking_directive(prompt)
        if removed_legacy_directive:
            logger.warning(f"[OLLAMA] operation={operation} model='{model}' prompt_directive=REMOVED")
        prompt_hash = hashlib.sha256(request_prompt.encode("utf-8")).hexdigest()
        if not settings.LLM_ENABLED:
            logger.info(f"[OLLAMA] operation={operation} model='{model}' status=DISABLED_FALLBACK")
            cls._trace(
                operation=operation,
                model=model,
                prompt_version=prompt_version,
                prompt_hash=prompt_hash,
                source_hash=cache_key,
                cache_status="BYPASS",
                validation_status="NOT_RUN",
                fallback_used=True,
                error_class="LLMDisabled",
            )
            return None

        resolved_cache_key = cache_key or LLMCacheRepository.extraction_cache_key(
            document_hash=hashlib.sha256(request_prompt.encode("utf-8")).hexdigest(),
            prompt_version=prompt_version,
            model_version=model,
            extraction_version=f"{settings.EXTRACTION_PARSER_VERSION}:{settings.EXTRACTION_SCHEMA_VERSION}",
        )

        cached_entry = LLMCacheRepository.get_cached_entry(resolved_cache_key)
        if cached_entry is not None:
            try:
                cached = response_model.model_validate(cached_entry.structured_data)
                _metrics.record_llm_call_prevented()
                logger.info(f"[OLLAMA] operation={operation} model='{model}' cache=HIT")
                if profiler:
                    profiler.metrics.cache_hit = True
                    profiler.metrics.ollama_request_ms = cached_entry.processing_time_ms
                    profiler.metrics.model_inference_ms = cached_entry.inference_time_ms
                    profiler.metrics.token_count = cached_entry.token_count
                cls._trace(
                    operation=operation,
                    model=model,
                    prompt_version=prompt_version,
                    prompt_hash=prompt_hash,
                    source_hash=resolved_cache_key,
                    cache_status="HIT",
                    validation_status="VALID",
                    fallback_used=False,
                    duration_ms=cached_entry.processing_time_ms,
                    inference_ms=float(cached_entry.inference_time_ms),
                    output_tokens=cached_entry.token_count,
                )
                return cached
            except (ValidationError, TypeError, ValueError) as exc:
                logger.warning(f"[OLLAMA] operation={operation} model='{model}' cache=INVALID error={type(exc).__name__}")
        else:
            logger.info(f"[OLLAMA] operation={operation} model='{model}' cache=MISS")

        supports_thinking = cls._supports_thinking(model)
        resolved_think = think if supports_thinking else None
        if think and not supports_thinking:
            logger.info(f"[OLLAMA] operation={operation} model='{model}' thinking=UNSUPPORTED_OMITTED")
        payload = OllamaTransport.build_generation_payload(
            model=model,
            prompt=request_prompt,
            response_schema=response_model.model_json_schema(),
            think=resolved_think,
            options=options,
        )

        def parse(data: dict[str, Any]) -> _StructuredGeneration:
            envelope = OllamaGenerateEnvelope.model_validate(data)
            if envelope.done_reason.lower() == "length":
                raise OllamaInvalidResponseError(
                    "Ollama generation reached the output limit and is incomplete.",
                    operation=operation,
                )
            raw_response = envelope.response.strip() or envelope.thinking.strip()
            structured_data = OllamaTransport.extract_json(raw_response, operation=operation)
            if not isinstance(structured_data, dict):
                raise ValueError("Structured generation must decode to a JSON object.")
            validation_started = time.perf_counter()
            validated = response_model.model_validate(structured_data)
            validation_ms = round((time.perf_counter() - validation_started) * 1000.0, 2)
            return _StructuredGeneration(
                validated=validated,
                structured_data=structured_data,
                raw_response=raw_response,
                reasoning=envelope.thinking,
                envelope=envelope,
                validation_ms=validation_ms,
            )

        prompt_chars = len(request_prompt)
        logger.info(
            f"[OLLAMA] operation={operation} model='{model}' status=CALLING "
            f"prompt_chars={prompt_chars} estimated_tokens={max(1, prompt_chars // 4)}"
        )
        llm_started = time.perf_counter()
        try:
            transport_result = OllamaTransport.generate(
                operation=operation,
                payload=payload,
                parser=parse,
            )
        except OllamaError as exc:
            duration_ms = round((time.perf_counter() - llm_started) * 1000.0, 2)
            logger.error(
                f"[OLLAMA] operation={operation} model='{model}' status=FALLBACK "
                f"error={type(exc).__name__} status_code={getattr(exc, 'status_code', 'none')} "
                f"retryable={exc.retryable} duration_ms={duration_ms} prompt_chars={prompt_chars} detail={exc}"
            )
            if profiler:
                profiler.metrics.ollama_request_ms = duration_ms
            cls._trace(
                operation=operation,
                model=model,
                prompt_version=prompt_version,
                prompt_hash=prompt_hash,
                source_hash=resolved_cache_key,
                cache_status="MISS",
                validation_status="INVALID" if "InvalidResponse" in type(exc).__name__ or "Schema" in type(exc).__name__ else "NOT_RUN",
                fallback_used=True,
                duration_ms=duration_ms,
                input_tokens=max(1, prompt_chars // 4),
                error_class=type(exc).__name__,
            )
            return None

        generation = transport_result.value
        inference_ms = round(generation.envelope.eval_duration / 1_000_000.0, 2) if generation.envelope.eval_duration else transport_result.duration_ms
        if profiler:
            profiler.metrics.ollama_request_ms = transport_result.duration_ms
            profiler.metrics.model_inference_ms = inference_ms
            profiler.metrics.token_count = generation.envelope.eval_count
            profiler.metrics.json_validation_ms = generation.validation_ms
            profiler.metrics.prompt_output_tokens = generation.envelope.eval_count
            profiler.metrics.prompt_input_tokens = generation.envelope.prompt_eval_count or profiler.metrics.prompt_input_tokens

        logger.info(
            f"[OLLAMA] operation={operation} model='{model}' status=SUCCESS "
            f"duration_ms={transport_result.duration_ms} "
            f"input_tokens={generation.envelope.prompt_eval_count} "
            f"output_tokens={generation.envelope.eval_count} "
            f"inference_ms={inference_ms}"
        )

        cls._trace(
            operation=operation,
            model=model,
            prompt_version=prompt_version,
            prompt_hash=prompt_hash,
            source_hash=resolved_cache_key,
            cache_status="MISS",
            validation_status="VALID",
            fallback_used=False,
            duration_ms=transport_result.duration_ms,
            inference_ms=inference_ms,
            validation_ms=generation.validation_ms,
            attempts=transport_result.attempts,
            input_tokens=generation.envelope.prompt_eval_count,
            output_tokens=generation.envelope.eval_count,
            completion_reason=generation.envelope.done_reason,
        )

        LLMCacheRepository.save_cached_entry(
            resolved_cache_key,
            LLMCacheEntry(
                prompt=request_prompt,
                raw_response=generation.raw_response,
                structured_data=generation.structured_data,
                reasoning=generation.reasoning,
                processing_time_ms=transport_result.duration_ms,
                token_count=generation.envelope.eval_count,
                inference_time_ms=int(inference_ms),
                model=model,
                prompt_version=prompt_version,
            ),
        )
        return cast(TModel, generation.validated)

    @staticmethod
    def unload_model(model_name: str | None = None) -> bool:
        """Compatibility operation for explicit lifecycle and shutdown cleanup."""
        if model_name is None and not settings.LLM_ENABLED:
            return False
        model = model_name or settings.OLLAMA_MODEL
        try:
            OllamaTransport.unload(model)
            return True
        except OllamaError as exc:
            logger.warning(f"[OLLAMA] operation=unload model='{model}' status=FALLBACK error={type(exc).__name__}")
            return False

    @staticmethod
    def close_transport() -> None:
        OllamaTransport.close()

    @staticmethod
    def get_transport_metrics() -> dict[str, Any]:
        return OllamaTransport.get_metrics()
