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
from app.repositories.llm_cache import LLMCacheEntry, LLMCacheRepository
from app.schemas.analysis import (
    DynamicMappingResponse,
    OptimizedLLMMatchResponse,
    QwenCVAnalysis,
)
from app.schemas.profile import DynamicCandidateProfile
from app.services.ollama_transport import (
    OllamaError,
    OllamaGenerateEnvelope,
    OllamaTransport,
)

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
    @classmethod
    def check_health(cls) -> bool:
        try:
            OllamaTransport.get_tags()
            return True
        except OllamaError as exc:
            logger.warning(f"[OLLAMA] operation=health status=FALLBACK error={type(exc).__name__}")
            return False

    @classmethod
    def get_available_models(cls) -> list[str]:
        try:
            result = OllamaTransport.get_tags()
            return [model.name for model in result.value.models]
        except OllamaError as exc:
            logger.warning(f"[OLLAMA] operation=tags status=FALLBACK error={type(exc).__name__}")
            return []

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
            options={"num_predict": 2048, "num_ctx": 4096, "temperature": 0.0},
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
            options={"num_predict": 2048, "num_ctx": 4096, "temperature": 0.0},
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
            options={"num_predict": 2048, "num_ctx": 4096, "temperature": 0.0},
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
                "num_predict": 4096,
                "num_ctx": 8192,
                "temperature": 0.0,
                "top_p": 0.9,
            },
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
        if not settings.LLM_ENABLED:
            logger.info(f"[OLLAMA] operation={operation} model='{model}' status=DISABLED_FALLBACK")
            return None

        resolved_cache_key = cache_key or LLMCacheRepository.extraction_cache_key(
            document_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
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
                return cached
            except (ValidationError, TypeError, ValueError) as exc:
                logger.warning(f"[OLLAMA] operation={operation} model='{model}' cache=INVALID error={type(exc).__name__}")
        else:
            logger.info(f"[OLLAMA] operation={operation} model='{model}' cache=MISS")

        directive = "/think" if think else "/no_think"
        normalized_prompt = prompt if prompt.startswith(directive) else f"{directive}\n{prompt}"
        payload = OllamaTransport.build_generation_payload(
            model=model,
            prompt=normalized_prompt,
            response_schema=response_model.model_json_schema(),
            think=think,
            options=options,
        )

        def parse(data: dict[str, Any]) -> _StructuredGeneration:
            envelope = OllamaGenerateEnvelope.model_validate(data)
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

        try:
            transport_result = OllamaTransport.generate(
                operation=operation,
                payload=payload,
                parser=parse,
            )
        except OllamaError as exc:
            logger.error(f"[OLLAMA] operation={operation} model='{model}' status=FALLBACK error={type(exc).__name__}")
            return None

        generation = transport_result.value
        inference_ms = round(generation.envelope.eval_duration / 1_000_000.0, 2) if generation.envelope.eval_duration else transport_result.duration_ms
        if profiler:
            profiler.metrics.ollama_request_ms = transport_result.duration_ms
            profiler.metrics.model_inference_ms = inference_ms
            profiler.metrics.token_count = generation.envelope.eval_count
            profiler.metrics.json_validation_ms = generation.validation_ms

        LLMCacheRepository.save_cached_entry(
            resolved_cache_key,
            LLMCacheEntry(
                prompt=normalized_prompt,
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
        """Compatibility operation for explicit lifecycle shutdowns; no longer called per CV."""
        if not settings.LLM_ENABLED:
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
