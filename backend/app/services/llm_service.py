import json
import time

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import logger
from app.core.profiler import PipelineProfiler
from app.repositories.llm_cache import LLMCacheEntry, LLMCacheRepository
from app.schemas.analysis import (
    DynamicMappingResponse,
    OptimizedLLMMatchResponse,
    QwenCVAnalysis,
)
from app.schemas.profile import DynamicCandidateProfile

_httpx_client_instance: httpx.Client | None = None


def _get_httpx_client(timeout: float = 600.0) -> httpx.Client:
    global _httpx_client_instance
    if _httpx_client_instance is None or _httpx_client_instance.is_closed:
        _httpx_client_instance = httpx.Client(
            timeout=httpx.Timeout(timeout=timeout, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
    return _httpx_client_instance


class OllamaLLMService:
    @staticmethod
    def extract_candidate_profile(
        prompt: str,
        prompt_version: str,
        cache_key: str = "",
    ) -> DynamicCandidateProfile | None:
        if not settings.LLM_ENABLED:
            logger.info("LLM semantic analysis is disabled via config.")
            return None

        model_name = settings.OLLAMA_MODEL

        if not cache_key:
            from app.repositories.llm_cache import LLMCacheRepository as LR
            cache_key = LR.extraction_cache_key(
                prompt_version=prompt_version,
                model_version=model_name,
            )

        # Check Cache First using full entry
        cached_entry = LLMCacheRepository.get_cached_entry(cache_key)
        if cached_entry is not None:
            logger.info(
                f"LLM Cache HIT for profile extraction '{model_name}' (v{prompt_version}). Skipping inference."
            )
            return DynamicCandidateProfile(**cached_entry.structured_data)

        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "format": DynamicCandidateProfile.model_json_schema(),
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "options": {
                "num_predict": 2048,
                "num_ctx": 4096,
                "temperature": 0.1,
            },
        }

        timeout_cfg = httpx.Timeout(timeout=settings.OLLAMA_REQUEST_TIMEOUT, connect=2.0)

        for attempt in range(1, settings.OLLAMA_MAX_RETRIES + 1):
            start_time = time.time()
            try:
                with httpx.Client(timeout=timeout_cfg) as client:
                    response = client.post(url, json=payload)
                    response.raise_for_status()

                duration_ms = int((time.time() - start_time) * 1000)

                data = response.json()
                response_text = data.get("response", "").strip() or data.get("thinking", "").strip()
                reasoning = data.get("thinking", "")
                raw_response = response_text

                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                elif response_text.startswith("```"):
                    response_text = response_text[3:]
                response_text = response_text.removesuffix("```")
                response_text = response_text.strip()

                parsed_json = json.loads(response_text)
                validated_result = DynamicCandidateProfile(**parsed_json)

                logger.info(
                    f"LLM Profile Extraction SUCCESS: model '{model_name}' (v{prompt_version}) took {duration_ms}ms."
                )

                entry = LLMCacheEntry(
                    prompt=prompt,
                    raw_response=raw_response,
                    structured_data=parsed_json,
                    reasoning=reasoning,
                    processing_time_ms=duration_ms,
                    token_count=data.get("eval_count", 0),
                    inference_time_ms=int(data.get("eval_duration", 0) / 1_000_000),
                    model=model_name,
                    prompt_version=prompt_version,
                )
                LLMCacheRepository.save_cached_entry(cache_key, entry)

                return validated_result

            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError) as exc:
                logger.warning(f"Ollama connection error (service down or unreachable): {exc}")
                break
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                logger.warning(f"Ollama HTTP error on attempt {attempt}: {exc}")
            except json.JSONDecodeError as exc:
                logger.warning(
                    f"Ollama JSON decode error on attempt {attempt}. Raw: {response_text[:100]}... Error: {exc}"
                )
            except ValidationError as exc:
                logger.warning(
                    f"Ollama Pydantic validation error on attempt {attempt}: {exc}"
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"Unexpected error calling Ollama on attempt {attempt}: {exc}", exc_info=True
                )

            if attempt == settings.OLLAMA_MAX_RETRIES:
                logger.error(
                    f"Failed to extract profile from Ollama after {settings.OLLAMA_MAX_RETRIES} attempts."
                )
                return None

        return None

    @staticmethod
    def call_qwen(
        prompt: str,
        prompt_version: str,
        cache_key: str = "",
    ) -> QwenCVAnalysis | None:
        if not settings.LLM_ENABLED:
            logger.info("LLM semantic analysis is disabled via config.")
            return None

        model_name = settings.OLLAMA_MODEL

        if not cache_key:
            from app.repositories.llm_cache import LLMCacheRepository as LR
            cache_key = LR.extraction_cache_key(
                prompt_version=prompt_version,
                model_version=model_name,
            )

        # Check Cache First using full entry
        cached_entry = LLMCacheRepository.get_cached_entry(cache_key)
        if cached_entry is not None:
            logger.info(
                f"LLM Cache HIT for model '{model_name}' (v{prompt_version}). Skipping inference."
            )
            return QwenCVAnalysis(**cached_entry.structured_data)

        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "format": QwenCVAnalysis.model_json_schema(),
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "options": {
                "num_predict": 2048,
                "num_ctx": 4096,
                "temperature": 0.1,
            },
        }

        for attempt in range(1, settings.OLLAMA_MAX_RETRIES + 1):
            start_time = time.time()
            try:
                with httpx.Client(timeout=settings.OLLAMA_REQUEST_TIMEOUT) as client:
                    response = client.post(url, json=payload)
                    response.raise_for_status()

                duration_ms = int((time.time() - start_time) * 1000)

                data = response.json()
                response_text = data.get("response", "").strip() or data.get("thinking", "").strip()
                reasoning = data.get("thinking", "")
                raw_response = response_text

                # Cleanup potential markdown wrapper if Qwen ignored instructions
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                elif response_text.startswith("```"):
                    response_text = response_text[3:]
                response_text = response_text.removesuffix("```")
                response_text = response_text.strip()

                parsed_json = json.loads(response_text)
                validated_result = QwenCVAnalysis(**parsed_json)

                logger.info(
                    f"LLM Inference SUCCESS: model '{model_name}' (v{prompt_version}) took {duration_ms}ms."
                )

                entry = LLMCacheEntry(
                    prompt=prompt,
                    raw_response=raw_response,
                    structured_data=parsed_json,
                    reasoning=reasoning,
                    processing_time_ms=duration_ms,
                    token_count=data.get("eval_count", 0),
                    inference_time_ms=int(data.get("eval_duration", 0) / 1_000_000),
                    model=model_name,
                    prompt_version=prompt_version,
                )
                LLMCacheRepository.save_cached_entry(cache_key, entry)

                return validated_result

            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError) as exc:
                logger.warning(f"Ollama connection error (service down or unreachable): {exc}")
                break
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                logger.warning(f"Ollama HTTP error on attempt {attempt}: {exc}")
            except json.JSONDecodeError as exc:
                logger.warning(
                    f"Ollama JSON decode error on attempt {attempt}. Raw: {response_text[:100]}... Error: {exc}"
                )
            except ValidationError as exc:
                logger.warning(
                    f"Ollama Pydantic validation error on attempt {attempt}: {exc}"
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"Unexpected error calling Ollama on attempt {attempt}: {exc}", exc_info=True
                )

            if attempt == settings.OLLAMA_MAX_RETRIES:
                logger.error(
                    f"Failed to get valid response from Ollama after {settings.OLLAMA_MAX_RETRIES} attempts."
                )
                return None

        return None

    @staticmethod
    def call_qwen_dynamic(
        prompt: str,
        prompt_version: str,
        cache_key: str = "",
    ) -> DynamicMappingResponse | None:
        if not settings.LLM_ENABLED:
            logger.info("LLM semantic analysis is disabled via config.")
            return None

        model_name = settings.OLLAMA_MODEL

        if not cache_key:
            from app.repositories.llm_cache import LLMCacheRepository as LR
            cache_key = LR.extraction_cache_key(
                prompt_version=prompt_version,
                model_version=model_name,
            )

        # Check Cache First using full entry
        cached_entry = LLMCacheRepository.get_cached_entry(cache_key)
        if cached_entry is not None:
            logger.info(
                f"LLM Cache HIT for dynamic mapping model '{model_name}' (v{prompt_version}). Skipping inference."
            )
            return DynamicMappingResponse(**cached_entry.structured_data)

        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "format": DynamicMappingResponse.model_json_schema(),
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "options": {
                "num_predict": 2048,
                "num_ctx": 4096,
                "temperature": 0.1,
            },
        }

        for attempt in range(1, settings.OLLAMA_MAX_RETRIES + 1):
            start_time = time.time()
            try:
                with httpx.Client(timeout=settings.OLLAMA_REQUEST_TIMEOUT) as client:
                    response = client.post(url, json=payload)
                    response.raise_for_status()

                duration_ms = int((time.time() - start_time) * 1000)

                data = response.json()
                response_text = data.get("response", "").strip() or data.get("thinking", "").strip()
                reasoning = data.get("thinking", "")
                raw_response = response_text

                # Cleanup potential markdown wrapper if Qwen ignored instructions
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                elif response_text.startswith("```"):
                    response_text = response_text[3:]
                response_text = response_text.removesuffix("```")
                response_text = response_text.strip()

                parsed_json = json.loads(response_text)
                validated_result = DynamicMappingResponse(**parsed_json)

                logger.info(
                    f"LLM Inference SUCCESS: dynamic mapping model '{model_name}' (v{prompt_version}) took {duration_ms}ms."
                )

                entry = LLMCacheEntry(
                    prompt=prompt,
                    raw_response=raw_response,
                    structured_data=parsed_json,
                    reasoning=reasoning,
                    processing_time_ms=duration_ms,
                    token_count=data.get("eval_count", 0),
                    inference_time_ms=int(data.get("eval_duration", 0) / 1_000_000),
                    model=model_name,
                    prompt_version=prompt_version,
                )
                LLMCacheRepository.save_cached_entry(cache_key, entry)

                return validated_result

            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError) as exc:
                logger.warning(f"Ollama connection error (service down or unreachable): {exc}")
                break
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                logger.warning(f"Ollama HTTP error on attempt {attempt}: {exc}")
            except json.JSONDecodeError as exc:
                logger.warning(
                    f"Ollama JSON decode error on attempt {attempt}. Error: {exc}\n"
                    f"Tail of response: {response_text[-200:] if len(response_text) > 200 else response_text}"
                )
            except ValidationError as exc:
                logger.warning(
                    f"Ollama Pydantic validation error on attempt {attempt}: {exc}"
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"Unexpected error calling Ollama on attempt {attempt}: {exc}", exc_info=True
                )

            if attempt == settings.OLLAMA_MAX_RETRIES:
                logger.error(
                    f"Failed to get valid response from Ollama after {settings.OLLAMA_MAX_RETRIES} attempts."
                )
                return None

        return None

    @classmethod
    def run_optimized_match(
        cls,
        prompt: str,
        prompt_version: str,
        cache_key: str,
        profiler: PipelineProfiler | None = None,
    ) -> OptimizedLLMMatchResponse | None:
        model_name = settings.OLLAMA_MODEL

        # 1. Check Cache using full entry (preserves metadata on hit)
        cached_entry = LLMCacheRepository.get_cached_entry(cache_key)
        if cached_entry is not None:
            logger.info(
                f"LLM Cache HIT for optimized match '{model_name}' (v{prompt_version}). "
                f"Skipping HTTP request."
            )
            if profiler:
                profiler.metrics.cache_hit = True
                profiler.metrics.ollama_request_ms = cached_entry.processing_time_ms
                profiler.metrics.model_inference_ms = cached_entry.inference_time_ms
                profiler.metrics.token_count = cached_entry.token_count
            return OptimizedLLMMatchResponse(**cached_entry.structured_data)

        if not settings.LLM_ENABLED:
            logger.info("LLM semantic analysis is disabled via config.")
            return None

        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "format": OptimizedLLMMatchResponse.model_json_schema(),
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "options": {
                "num_predict": 4096,
                "num_ctx": 8192,
                "temperature": 0.1,
                "top_p": 0.9,
            },
        }

        httpx.Timeout(timeout=settings.OLLAMA_REQUEST_TIMEOUT, connect=5.0)

        for attempt in range(1, settings.OLLAMA_MAX_RETRIES + 1):
            t_req_start = time.perf_counter()
            logger.info(
                f"Sending LLM request to Ollama model '{model_name}' (v{prompt_version}) | "
                f"Prompt: {len(prompt)} chars | Attempt {attempt}/{settings.OLLAMA_MAX_RETRIES}..."
            )
            try:
                client = _get_httpx_client(settings.OLLAMA_REQUEST_TIMEOUT)
                response = client.post(url, json=payload)
                response.raise_for_status()

                req_duration_ms = round((time.perf_counter() - t_req_start) * 1000.0, 2)
                data = response.json()

                eval_count = data.get("eval_count", 0)
                eval_duration_ns = data.get("eval_duration", 0)
                inference_ms = (
                    round(eval_duration_ns / 1_000_000.0, 2)
                    if eval_duration_ns
                    else req_duration_ms
                )

                if profiler:
                    profiler.metrics.ollama_request_ms = req_duration_ms
                    profiler.metrics.model_inference_ms = inference_ms
                    if eval_count:
                        profiler.metrics.token_count = eval_count

                response_text = data.get("response", "").strip() or data.get("thinking", "").strip()
                reasoning = data.get("thinking", "")
                raw_response = response_text
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                elif response_text.startswith("```"):
                    response_text = response_text[3:]
                response_text = response_text.removesuffix("```").strip()

                t_val_start = time.perf_counter()
                parsed_json = json.loads(response_text)
                validated_result = OptimizedLLMMatchResponse(**parsed_json)
                val_duration_ms = round((time.perf_counter() - t_val_start) * 1000.0, 2)

                if profiler:
                    profiler.metrics.json_validation_ms = val_duration_ms

                logger.info(
                    f"LLM Optimized Match SUCCESS: model '{model_name}' (v{prompt_version}) "
                    f"req_time={req_duration_ms}ms, inference_time={inference_ms}ms."
                )

                # Save full cache entry with all metadata
                entry = LLMCacheEntry(
                    prompt=prompt,
                    raw_response=raw_response,
                    structured_data=parsed_json,
                    reasoning=reasoning,
                    processing_time_ms=req_duration_ms,
                    token_count=eval_count,
                    inference_time_ms=int(inference_ms) if inference_ms else 0,
                    model=model_name,
                    prompt_version=prompt_version,
                )
                LLMCacheRepository.save_cached_entry(cache_key, entry)
                return validated_result

            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError) as exc:
                logger.warning(f"Ollama connection error (service down or unreachable): {exc}")
                break
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                logger.warning(f"Ollama HTTP error on attempt {attempt}: {exc}")
            except json.JSONDecodeError as exc:
                raw_snip = response_text[:500] + ("..." if len(response_text) > 500 else "")
                logger.warning(
                    f"Ollama JSON decode error on attempt {attempt}. Raw: {raw_snip}\nError: {exc}"
                )
            except ValidationError as exc:
                logger.warning(
                    f"Ollama Pydantic validation error on attempt {attempt}: {exc}"
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"Unexpected error calling Ollama on attempt {attempt}: {exc}", exc_info=True
                )

            if attempt == settings.OLLAMA_MAX_RETRIES:
                logger.error(
                    f"Failed to get valid OptimizedLLMMatchResponse from Ollama after {settings.OLLAMA_MAX_RETRIES} attempts."
                )
                return None

        return None

