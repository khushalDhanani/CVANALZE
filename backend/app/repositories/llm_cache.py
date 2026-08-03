from dataclasses import asdict, dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.cache import CacheKey, llm_cache_manager
from app.core.logging import logger

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMCacheEntry:
    """Full LLM inference cache entry with all metadata preserved."""

    prompt: str
    raw_response: str
    structured_data: dict[str, Any]
    reasoning: str
    processing_time_ms: float
    token_count: int
    inference_time_ms: int
    model: str
    prompt_version: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["__entry__"] = True
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLMCacheEntry":
        return cls(
            prompt=data["prompt"],
            raw_response=data.get("raw_response", ""),
            structured_data=data.get("structured_data", {}),
            reasoning=data.get("reasoning", ""),
            processing_time_ms=data.get("processing_time_ms", 0.0),
            token_count=data.get("token_count", 0),
            inference_time_ms=data.get("inference_time_ms", 0),
            model=data.get("model", ""),
            prompt_version=data.get("prompt_version", ""),
        )


class LLMCacheRepository:
    """
    Repository to cache LLM inference results using version-aware,
    deterministic cache keys composed from document hash, candidate ID,
    vacancy IDs, prompt version, model version, and extraction/matching
    version fields — never raw prompt text.
    Delegates all storage to CacheManager (Redis L2 + File L3).
    """

    @classmethod
    def compute_composite_hash(
        cls,
        document_hash: str = "",
        candidate_id: str = "",
        vacancy_ids: list[str] | None = None,
        vacancy_version: str = "",
        prompt_version: str = "",
        model_version: str = "",
        extraction_version: str = "",
        matching_version: str = "",
    ) -> str:
        return CacheKey.for_llm_match(
            document_hash=document_hash,
            candidate_id=candidate_id,
            vacancy_ids=vacancy_ids,
            vacancy_version=vacancy_version,
            prompt_version=prompt_version,
            model_version=model_version,
            extraction_version=extraction_version,
            matching_version=matching_version,
        ).to_key()

    @classmethod
    def extraction_cache_key(
        cls,
        document_hash: str = "",
        candidate_id: str = "",
        prompt_version: str = "",
        model_version: str = "",
        extraction_version: str = "",
    ) -> str:
        return CacheKey.for_llm_extraction(
            document_hash=document_hash,
            candidate_id=candidate_id,
            prompt_version=prompt_version,
            model_version=model_version,
            extraction_version=extraction_version,
        ).to_key()

    @classmethod
    def get_cached_object(cls, hash_key: str, model_class: type[T]) -> T | None:
        entry = cls.get_cached_entry(hash_key)
        if entry is not None:
            try:
                return model_class(**entry.structured_data)
            except Exception as exc:
                logger.warning(f"Failed to deserialize cached object ({hash_key}): {exc}")
                return None
        return None

    @classmethod
    def save_cached_object(cls, hash_key: str, object_to_cache: BaseModel | dict[str, Any]) -> None:
        if isinstance(object_to_cache, BaseModel):
            data = object_to_cache.model_dump()
        elif isinstance(object_to_cache, dict):
            data = object_to_cache
        else:
            data = object_to_cache
        llm_cache_manager.set(hash_key, data)

    @classmethod
    def get_cached_entry(cls, hash_key: str) -> LLMCacheEntry | None:
        data = llm_cache_manager.get(hash_key)
        if data is not None and isinstance(data, dict):
            if data.get("__entry__"):
                return LLMCacheEntry.from_dict(data)
            # Backward compatibility: old-style entry stored by save_cached_object
            # without __entry__ marker — wrap into LLMCacheEntry.
            return LLMCacheEntry(
                prompt="",
                raw_response="",
                structured_data=data,
                reasoning="",
                processing_time_ms=0.0,
                token_count=0,
                inference_time_ms=0,
                model="",
                prompt_version="",
            )
        return None

    @classmethod
    def save_cached_entry(cls, hash_key: str, entry: LLMCacheEntry) -> None:
        llm_cache_manager.set(hash_key, entry.to_dict())

    @classmethod
    def get_cached_result(cls, cache_key: str) -> Any | None:
        return llm_cache_manager.get(cache_key)

    @classmethod
    def save_result(
        cls,
        cache_key: str,
        result: Any,
    ) -> None:
        llm_cache_manager.set(cache_key, result)
