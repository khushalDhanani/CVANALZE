import hashlib
import json
from pathlib import Path
from typing import Any, TypeVar

import redis
from filelock import FileLock
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import logger

T = TypeVar("T", bound=BaseModel)

_redis_client = None
if settings.REDIS_URL:
    try:
        _redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception as exc:
        _redis_client = None


class LLMCacheRepository:
    """
    Repository to cache LLM inference results based on composite hashes
    (CV hash, vacancy set hash, prompt version, and model name).
    """

    @classmethod
    def _get_cache_dir(cls) -> Path:
        cache_dir = settings.UPLOADS_DIR / ".llm_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    @classmethod
    def compute_composite_hash(
        cls,
        cv_text: str,
        vacancies: list[dict[str, Any]],
        prompt_version: str,
        model_name: str,
    ) -> str:
        cv_hash = hashlib.sha256(cv_text.encode("utf-8")).hexdigest()
        vac_ids_and_reqs = [
            f"{v.get('vacancy_id') or v.get('id')}:{v.get('title')}:{v.get('required_skills')}"
            for v in vacancies
        ]
        vac_hash = hashlib.sha256(json.dumps(sorted(vac_ids_and_reqs)).encode("utf-8")).hexdigest()
        raw_key = f"{cv_hash}:{vac_hash}:{prompt_version}:{model_name}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @classmethod
    def _compute_hash(
        cls, model_name: str, prompt_version: str, prompt_text: str
    ) -> str:
        cache_key_raw = f"{model_name}|{prompt_version}|{prompt_text}"
        return hashlib.sha256(cache_key_raw.encode("utf-8")).hexdigest()

    @classmethod
    def _get_file_path(cls, hash_key: str) -> Path:
        return cls._get_cache_dir() / f"{hash_key}.json"

    @classmethod
    def get_cached_object(
        cls, hash_key: str, model_class: type[T]
    ) -> T | None:
        if _redis_client:
            try:
                payload = _redis_client.get(f"llm_cache:{hash_key}")
                if payload:
                    data = json.loads(payload)
                    return model_class(**data)
            except Exception as exc:
                logger.warning(f"Redis cache read failed for {hash_key}: {exc}")

        file_path = cls._get_file_path(hash_key)
        if file_path.exists():
            try:
                lock = FileLock(file_path.with_suffix(".lock"))
                with lock.acquire(timeout=5.0):
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                    return model_class(**data)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Failed to read object from LLM cache ({hash_key}): {exc}")
                return None
        return None

    @classmethod
    def save_cached_object(
        cls, hash_key: str, object_to_cache: BaseModel | dict[str, Any]
    ) -> None:
        if isinstance(object_to_cache, BaseModel):
            json_str = object_to_cache.model_dump_json(indent=2)
        else:
            json_str = json.dumps(object_to_cache, indent=2, ensure_ascii=False)
            
        if _redis_client:
            try:
                _redis_client.set(f"llm_cache:{hash_key}", json_str)
                _redis_client.expire(f"llm_cache:{hash_key}", 2592000) # 30 days
            except Exception as exc:
                logger.warning(f"Redis cache write failed for {hash_key}: {exc}")
                
        file_path = cls._get_file_path(hash_key)
        try:
            lock = FileLock(file_path.with_suffix(".lock"))
            with lock.acquire(timeout=5.0):
                file_path.write_text(json_str, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to write object to LLM cache ({hash_key}): {exc}")

    @classmethod
    def get_cached_result(
        cls, model_name: str, prompt_version: str, prompt_text: str
    ) -> Any | None:
        hash_key = cls._compute_hash(model_name, prompt_version, prompt_text)
        
        if _redis_client:
            try:
                payload = _redis_client.get(f"llm_cache:{hash_key}")
                if payload:
                    return json.loads(payload)
            except Exception as exc:
                logger.warning(f"Redis cache read failed for {hash_key}: {exc}")
                
        file_path = cls._get_file_path(hash_key)

        if file_path.exists():
            try:
                lock = FileLock(file_path.with_suffix(".lock"))
                with lock.acquire(timeout=5.0):
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                    return data
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Failed to read from LLM cache: {exc}")
                return None

        return None

    @classmethod
    def save_result(
        cls,
        model_name: str,
        prompt_version: str,
        prompt_text: str,
        result: Any,
    ) -> None:
        hash_key = cls._compute_hash(model_name, prompt_version, prompt_text)
        cls.save_cached_object(hash_key, result)
