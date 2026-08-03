import fnmatch
import hashlib
import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from filelock import FileLock

from app.core.config import settings
from app.core.logging import logger
from app.core.metrics import _metrics

_REDIS_CLIENT: Any = None
if settings.REDIS_URL:
    try:
        import redis as redis_module
        _REDIS_CLIENT = redis_module.Redis.from_url(
            settings.REDIS_URL, decode_responses=True
        )
        _REDIS_CLIENT.ping()
    except Exception:
        _REDIS_CLIENT = None


@dataclass(frozen=True)
class CacheKey:
    """Deterministic, version-aware cache key composed from named components.

    Produces a SHA-256 hex digest from sorted key=value pairs, ensuring
    automatic uniqueness and that keys change when any contributing
    component changes. Never uses raw prompt text as input.
    """
    components: dict[str, str] = field(default_factory=dict)

    def to_key(self) -> str:
        if not self.components:
            return ""
        sorted_items = sorted(self.components.items())
        raw = "|".join(f"{k}={v}" for k, v in sorted_items)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def for_llm_match(
        cls,
        document_hash: str = "",
        candidate_id: str = "",
        vacancy_ids: list[str] | None = None,
        vacancy_version: str = "",
        prompt_version: str = "",
        model_version: str = "",
        extraction_version: str = "",
        matching_version: str = "",
    ) -> "CacheKey":
        components: dict[str, str] = {}
        if document_hash:
            components["doc_hash"] = document_hash
        if candidate_id:
            components["cand_id"] = candidate_id
        if vacancy_ids:
            components["vac_ids"] = ",".join(sorted(str(v) for v in vacancy_ids))
        if vacancy_version:
            components["vac_ver"] = vacancy_version
        if prompt_version:
            components["prompt_ver"] = prompt_version
        if model_version:
            components["model_ver"] = model_version
        if extraction_version:
            components["extract_ver"] = extraction_version
        if matching_version:
            components["match_ver"] = matching_version
        return cls(components=components)

    @classmethod
    def for_match_result(
        cls,
        document_hash: str = "",
        candidate_id: str = "",
        vacancy_version: str = "",
        vacancy_ids: list[str] | None = None,
        prompt_version: str = "",
        model_version: str = "",
        extraction_version: str = "",
        matching_version: str = "",
    ) -> "CacheKey":
        components: dict[str, str] = {}
        if document_hash:
            components["doc_hash"] = document_hash
        if candidate_id:
            components["cand_id"] = candidate_id
        if vacancy_version:
            components["vac_ver"] = vacancy_version
        if vacancy_ids:
            components["vac_ids"] = ",".join(sorted(str(v) for v in vacancy_ids))
        if prompt_version:
            components["prompt_ver"] = prompt_version
        if model_version:
            components["model_ver"] = model_version
        if extraction_version:
            components["extract_ver"] = extraction_version
        if matching_version:
            components["match_ver"] = matching_version
        return cls(components=components)

    @classmethod
    def for_document_extraction(
        cls,
        document_hash: str,
        parser_version: str,
        schema_version: str,
    ) -> "CacheKey":
        return cls(
            components={
                "doc_hash": document_hash,
                "parser_ver": parser_version,
                "schema_ver": schema_version,
            }
        )

    @classmethod
    def for_llm_extraction(
        cls,
        document_hash: str = "",
        candidate_id: str = "",
        prompt_version: str = "",
        model_version: str = "",
        extraction_version: str = "",
    ) -> "CacheKey":
        components: dict[str, str] = {}
        if document_hash:
            components["doc_hash"] = document_hash
        if candidate_id:
            components["cand_id"] = candidate_id
        if prompt_version:
            components["prompt_ver"] = prompt_version
        if model_version:
            components["model_ver"] = model_version
        if extraction_version:
            components["extract_ver"] = extraction_version
        return cls(components=components)


class CacheProvider(ABC):
    @abstractmethod
    def get(self, key: str) -> Any | None:
        ...

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        ...

    @abstractmethod
    def delete_by_pattern(self, pattern: str) -> int:
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def ttl(self, key: str) -> int | None:
        ...

    @abstractmethod
    def clear(self) -> None:
        ...


class MemoryCache(CacheProvider):
    def __init__(self, max_size: int = 1000):
        self._store: dict[str, Any] = {}
        self._expiry: dict[str, float] = {}
        self._max_size = max_size

    def get(self, key: str) -> Any | None:
        raw = self._store.get(key)
        if raw is None:
            return None
        exp = self._expiry.get(key)
        if exp is not None and time.monotonic() > exp:
            self.delete(key)
            return None
        return raw

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        if len(self._store) >= self._max_size and key not in self._store:
            try:
                oldest = min(self._expiry, key=self._expiry.get) if self._expiry else next(iter(self._store))
                self.delete(oldest)
            except StopIteration:
                pass
        self._store[key] = value
        if ttl is not None:
            self._expiry[key] = time.monotonic() + ttl
        elif key in self._expiry:
            del self._expiry[key]

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._expiry.pop(key, None)

    def delete_by_pattern(self, pattern: str) -> int:
        count = 0
        for key in list(self._store.keys()):
            if self._match_pattern(key, pattern):
                self.delete(key)
                count += 1
        return count

    @staticmethod
    def _match_pattern(key: str, pattern: str) -> bool:
        if "*" not in pattern:
            return key == pattern
        return fnmatch.fnmatch(key, pattern)

    def exists(self, key: str) -> bool:
        raw = self._store.get(key)
        if raw is None:
            return False
        exp = self._expiry.get(key)
        if exp is not None and time.monotonic() > exp:
            self.delete(key)
            return False
        return True

    def ttl(self, key: str) -> int | None:
        exp = self._expiry.get(key)
        if exp is None:
            return None
        remaining = int(exp - time.monotonic())
        return max(0, remaining)

    def clear(self) -> None:
        self._store.clear()
        self._expiry.clear()


class RedisCache(CacheProvider):
    def __init__(self, key_prefix: str = ""):
        self._key_prefix = key_prefix

    @property
    def _client(self) -> Any:
        return _REDIS_CLIENT

    @property
    def available(self) -> bool:
        return _REDIS_CLIENT is not None

    def _prefixed(self, key: str) -> str:
        return f"{self._key_prefix}{key}" if self._key_prefix else key

    def get(self, key: str) -> Any | None:
        client = _REDIS_CLIENT
        if not client:
            return None
        try:
            val = client.get(self._prefixed(key))
            if val is not None:
                return json.loads(val)
            return None
        except Exception as exc:
            logger.warning(f"RedisCache.get({key}) failed: {exc}")
            return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        client = _REDIS_CLIENT
        if not client:
            return
        try:
            payload = json.dumps(value, ensure_ascii=False)
            prefixed = self._prefixed(key)
            if ttl is not None:
                client.setex(prefixed, ttl, payload)
            else:
                client.set(prefixed, payload)
        except Exception as exc:
            logger.warning(f"RedisCache.set({key}) failed: {exc}")

    def delete(self, key: str) -> None:
        client = _REDIS_CLIENT
        if not client:
            return
        try:
            client.delete(self._prefixed(key))
        except Exception as exc:
            logger.warning(f"RedisCache.delete({key}) failed: {exc}")

    def delete_by_pattern(self, pattern: str) -> int:
        client = _REDIS_CLIENT
        if not client:
            return 0
        count = 0
        try:
            cursor = 0
            prefixed = self._prefixed(pattern)
            while True:
                cursor, keys = client.scan(cursor=cursor, match=prefixed, count=1000)
                if keys:
                    client.delete(*keys)
                    count += len(keys)
                if cursor == 0:
                    break
        except Exception as exc:
            logger.warning(f"RedisCache.delete_by_pattern({pattern}) failed: {exc}")
        return count

    def exists(self, key: str) -> bool:
        client = _REDIS_CLIENT
        if not client:
            return False
        try:
            return bool(client.exists(self._prefixed(key)))
        except Exception as exc:
            logger.warning(f"RedisCache.exists({key}) failed: {exc}")
            return False

    def ttl(self, key: str) -> int | None:
        client = _REDIS_CLIENT
        if not client:
            return None
        try:
            remaining = client.ttl(self._prefixed(key))
            return max(0, remaining) if remaining is not None and remaining >= 0 else None
        except Exception as exc:
            logger.warning(f"RedisCache.ttl({key}) failed: {exc}")
            return None

    def clear(self) -> None:
        client = _REDIS_CLIENT
        if not client:
            return
        try:
            cursor = 0
            while True:
                cursor, keys = client.scan(cursor=cursor, match=f"{self._key_prefix}*")
                if keys:
                    client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:
            logger.warning(f"RedisCache.clear() failed: {exc}")


class FileCache(CacheProvider):
    def __init__(self, cache_dir: str | Path, key_prefix: str = ""):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._key_prefix = key_prefix

    def _sanitize_key(self, key: str) -> str:
        clean_key = key.split(":", 1)[1] if ":" in key else key
        if self._key_prefix and clean_key.startswith(self._key_prefix):
            clean_key = clean_key[len(self._key_prefix):]
        if clean_key.endswith(".json"):
            return clean_key
        return f"{clean_key}.json"

    def _path(self, key: str) -> Path:
        filename = self._sanitize_key(key)
        if self._key_prefix and not filename.startswith(self._key_prefix):
            filename = f"{self._key_prefix}{filename}"
        return self._cache_dir / filename

    def _lock_path(self, key: str) -> Path:
        path = self._path(key)
        return path.with_suffix(".lock")

    def get(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            lock = FileLock(self._lock_path(key))
            with lock.acquire(timeout=5.0):
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"FileCache.get({key}) failed: {exc}")
            return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        path = self._path(key)
        try:
            payload = json.dumps(value, indent=2, ensure_ascii=False)
            lock = FileLock(self._lock_path(key))
            with lock.acquire(timeout=5.0):
                path.write_text(payload, encoding="utf-8")
        except Exception as exc:
            logger.warning(f"FileCache.set({key}) failed: {exc}")

    def delete(self, key: str) -> None:
        path = self._path(key)
        lock_path = self._lock_path(key)
        try:
            if path.exists():
                path.unlink()
            if lock_path.exists():
                lock_path.unlink()
        except Exception as exc:
            logger.warning(f"FileCache.delete({key}) failed: {exc}")

    def delete_by_pattern(self, pattern: str) -> int:
        count = 0
        clean_pat = pattern
        if ":" in clean_pat:
            clean_pat = clean_pat.rsplit(":", 1)[-1]
        clean_pat = re.sub(r"\*+", "*", clean_pat)
        glob_pat = f"{self._key_prefix}*{clean_pat}" if not clean_pat.startswith("*") else f"{self._key_prefix}{clean_pat}"
        if not glob_pat.endswith(".json"):
            glob_pat = f"{glob_pat}.json"
        for f in self._cache_dir.glob(glob_pat):
            try:
                f.unlink()
                lock = self._cache_dir / f.with_suffix(".lock").name
                if lock.exists():
                    lock.unlink()
                count += 1
            except OSError:
                pass
        return count

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def ttl(self, key: str) -> int | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            age = time.time() - path.stat().st_mtime
            return max(0, int(age))
        except OSError:
            return None

    def clear(self) -> None:
        for f in self._cache_dir.glob(f"{self._key_prefix}*.json"):
            try:
                f.unlink()
            except OSError:
                pass
        for f in self._cache_dir.glob(f"{self._key_prefix}*.lock"):
            try:
                f.unlink()
            except OSError:
                pass


class CacheManager:
    def __init__(
        self,
        namespace: str,
        providers: list[CacheProvider],
        default_ttl: int | None = None,
        persist_to_all_providers: bool = False,
    ):
        self._namespace = namespace
        self._providers = providers
        self._default_ttl = default_ttl
        self._persist_to_all_providers = persist_to_all_providers

    def _make_key(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    @property
    def active_providers(self) -> list[CacheProvider]:
        """
        Dynamically yields active providers:
        Namespaces configured for persistence across all providers always use every tier.
        If RedisCache is present and available (_REDIS_CLIENT is not None), FileCache (L3)
        is bypassed during reads/writes to eliminate FileLock disk I/O bottlenecks.
        If RedisCache is down or unavailable, FileCache (L3) is retained as persistent fallback.
        Deletion operations (delete, delete_by_pattern, clear) always execute against all providers
        to ensure clean storage cleanup across all tiers.
        """
        if self._persist_to_all_providers:
            return self._providers
        has_active_redis = any(
            isinstance(p, RedisCache) and p.available for p in self._providers
        )
        if has_active_redis:
            return [p for p in self._providers if not isinstance(p, FileCache)]
        return self._providers

    def get(self, key: str, default: Any = None) -> Any:
        cache_key = self._make_key(key)
        t0 = time.monotonic()
        providers = self.active_providers
        for i, provider in enumerate(providers):
            val = provider.get(cache_key)
            if val is not None:
                elapsed = (time.monotonic() - t0) * 1000
                _metrics.record_hit(self._namespace)
                _metrics.record_lookup_time(self._namespace, elapsed)
                for j in range(i):
                    try:
                        providers[j].set(cache_key, val)
                    except Exception:
                        pass
                logger.info(f"CACHE HIT [{self._namespace}] key={key} ({elapsed:.1f}ms)")
                return val
        elapsed = (time.monotonic() - t0) * 1000
        _metrics.record_miss(self._namespace)
        _metrics.record_lookup_time(self._namespace, elapsed)
        logger.info(f"CACHE MISS [{self._namespace}] key={key} ({elapsed:.1f}ms)")
        return default

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        cache_key = self._make_key(key)
        effective_ttl = self._default_ttl if ttl is None else ttl
        t0 = time.monotonic()
        for provider in self.active_providers:
            try:
                provider.set(cache_key, value, effective_ttl)
            except Exception as exc:
                logger.warning(f"CacheManager.set({key}) provider {type(provider).__name__} failed: {exc}")
        elapsed = (time.monotonic() - t0) * 1000
        _metrics.record_set(self._namespace)
        _metrics.record_save_time(self._namespace, elapsed)
        logger.info(f"CACHE SET [{self._namespace}] key={key} ({elapsed:.1f}ms)")

    def delete(self, key: str) -> None:
        cache_key = self._make_key(key)
        for provider in self._providers:
            try:
                provider.delete(cache_key)
            except Exception as exc:
                logger.warning(f"CacheManager.delete({key}) provider {type(provider).__name__} failed: {exc}")
        _metrics.record_delete(self._namespace)
        logger.info(f"CACHE DELETE [{self._namespace}] key={key}")

    def delete_by_pattern(self, pattern: str) -> int:
        cache_pattern = self._make_key(pattern)
        total = 0
        for provider in self._providers:
            try:
                total += provider.delete_by_pattern(cache_pattern)
            except Exception as exc:
                logger.warning(f"CacheManager.delete_by_pattern({pattern}) provider {type(provider).__name__} failed: {exc}")
        _metrics.record_pattern_delete(self._namespace)
        if total:
            logger.info(f"CACHE DELETE BY PATTERN [{self._namespace}] pattern={pattern} count={total}")
        return total

    def exists(self, key: str) -> bool:
        cache_key = self._make_key(key)
        for provider in self.active_providers:
            try:
                if provider.exists(cache_key):
                    return True
            except Exception:
                pass
        return False

    def ttl(self, key: str) -> int | None:
        cache_key = self._make_key(key)
        for provider in self.active_providers:
            try:
                ttl_val = provider.ttl(cache_key)
                if ttl_val is not None:
                    return ttl_val
            except Exception:
                pass
        return None

    def clear(self) -> None:
        for provider in self._providers:
            try:
                provider.clear()
            except Exception as exc:
                logger.warning(f"CacheManager.clear() provider {type(provider).__name__} failed: {exc}")
        logger.info(f"CACHE CLEAR [{self._namespace}]")


class CacheIndex:
    """
    Redis and In-Memory secondary index for tracking which cache keys depend on
    which resource IDs, enabling selective invalidation without scanning.
    Index entries are SETs: ``cache_idx:{index_name}:{resource_id}`` containing cache keys.
    """

    _PREFIX = "cache_idx"
    _in_memory_index: dict[str, set[str]] = {}

    @classmethod
    def _client(cls) -> Any:
        return _REDIS_CLIENT

    @classmethod
    def add(cls, index_name: str, resource_id: str, cache_key: str) -> None:
        if not index_name or not resource_id or not cache_key:
            return
        idx_key = f"{cls._PREFIX}:{index_name}:{resource_id}"
        if idx_key not in cls._in_memory_index:
            cls._in_memory_index[idx_key] = set()
        cls._in_memory_index[idx_key].add(cache_key)

        client = cls._client()
        if client:
            try:
                client.sadd(idx_key, cache_key)
            except Exception as exc:
                logger.warning(f"CacheIndex.add({index_name}, {resource_id}) failed: {exc}")

    @classmethod
    def get_keys(cls, index_name: str, resource_id: str) -> set[str]:
        idx_key = f"{cls._PREFIX}:{index_name}:{resource_id}"
        keys = set(cls._in_memory_index.get(idx_key, set()))
        client = cls._client()
        if client:
            try:
                redis_keys = client.smembers(idx_key)
                if redis_keys:
                    keys.update(redis_keys)
            except Exception as exc:
                logger.warning(f"CacheIndex.get_keys({index_name}, {resource_id}) failed: {exc}")
        return keys

    @classmethod
    def remove(cls, index_name: str, resource_id: str) -> None:
        idx_key = f"{cls._PREFIX}:{index_name}:{resource_id}"
        cls._in_memory_index.pop(idx_key, None)
        client = cls._client()
        if client:
            try:
                client.delete(idx_key)
            except Exception as exc:
                logger.warning(f"CacheIndex.remove({index_name}, {resource_id}) failed: {exc}")

    @classmethod
    def remove_key(cls, index_name: str, resource_id: str, cache_key: str) -> None:
        idx_key = f"{cls._PREFIX}:{index_name}:{resource_id}"
        if idx_key in cls._in_memory_index:
            cls._in_memory_index[idx_key].discard(cache_key)
            if not cls._in_memory_index[idx_key]:
                del cls._in_memory_index[idx_key]
        client = cls._client()
        if client:
            try:
                client.srem(idx_key, cache_key)
            except Exception as exc:
                logger.warning(f"CacheIndex.remove_key({index_name}, {resource_id}) failed: {exc}")

    @classmethod
    def clear(cls) -> None:
        cls._in_memory_index.clear()


class CacheInvalidator:
    """
    Selective cache invalidation for each trigger.
    Uses CacheIndex (when available) to find and delete only the affected entries,
    falling back to pattern-based deletion on non-Redis providers.
    """

    @classmethod
    def invalidate_cv(cls, doc_hash: str) -> None:
        extraction_keys = CacheIndex.get_keys("doc_by_hash", doc_hash)
        for key in extraction_keys:
            doc_cache_manager.delete(key)
        CacheIndex.remove("doc_by_hash", doc_hash)
        doc_cache_manager.delete(doc_hash)
        doc_cache_manager.delete_by_pattern(f"*{doc_hash}*")
        cv_result_cache_manager.delete(doc_hash)
        cv_result_cache_manager.delete_by_pattern(f"*{doc_hash}*")
        embedding_cache_manager.delete_by_pattern(f"*:{doc_hash}*")
        llm_cache_manager.delete_by_pattern(f"*{doc_hash}*")
        cls._invalidate_match_results_by_doc(doc_hash)
        logger.info(f"[INVALIDATE] CV cache invalidated for doc_hash={doc_hash[:12]}...")

    @classmethod
    def invalidate_candidate(cls, candidate_id: str) -> None:
        cid = str(candidate_id).removeprefix("cand_")
        cls._invalidate_match_results_by_candidate(candidate_id)
        cls._invalidate_match_results_by_candidate(cid)
        cv_result_cache_manager.delete_by_pattern(f"*cand_{cid}*")
        cv_result_cache_manager.delete_by_pattern(f"*{candidate_id}*")
        logger.info(f"[INVALIDATE] Candidate cache invalidated for candidate_id={candidate_id}")

    @classmethod
    def invalidate_vacancies(cls) -> None:
        vacancy_cache_manager.delete("all_jobs")
        vacancy_cache_manager.delete("all_jobs_version")
        embedding_cache_manager.delete_by_pattern(f"{settings.EMBEDDING_MODEL}:vac:*")
        match_result_cache_manager.delete_by_pattern("*")
        logger.info("[INVALIDATE] Vacancy cache invalidated.")

    @classmethod
    def invalidate_prompt(cls) -> None:
        llm_cache_manager.delete_by_pattern("*")
        match_result_cache_manager.delete_by_pattern("*")
        logger.info("[INVALIDATE] Prompt cache invalidated.")

    @classmethod
    def invalidate_llm_model(cls) -> None:
        llm_cache_manager.delete_by_pattern("*")
        match_result_cache_manager.delete_by_pattern("*")
        logger.info("[INVALIDATE] LLM model cache invalidated.")

    @classmethod
    def invalidate_extraction(cls) -> None:
        doc_cache_manager.delete_by_pattern("*")
        llm_cache_manager.delete_by_pattern("*")
        match_result_cache_manager.delete_by_pattern("*")
        logger.info("[INVALIDATE] Extraction cache invalidated.")

    @classmethod
    def invalidate_embedding_model(cls) -> None:
        embedding_cache_manager.delete_by_pattern("*")
        match_result_cache_manager.delete_by_pattern("*")
        logger.info("[INVALIDATE] Embedding model cache invalidated.")

    @classmethod
    def _invalidate_match_results_by_doc(cls, doc_hash: str) -> None:
        keys = CacheIndex.get_keys("match_by_doc", doc_hash)
        for key in keys:
            match_result_cache_manager.delete(key)
        CacheIndex.remove("match_by_doc", doc_hash)
        if not keys:
            match_result_cache_manager.delete_by_pattern(f"*{doc_hash}*")

    @classmethod
    def _invalidate_match_results_by_candidate(cls, candidate_id: str) -> None:
        keys = CacheIndex.get_keys("match_by_cand", candidate_id)
        for key in keys:
            match_result_cache_manager.delete(key)
        CacheIndex.remove("match_by_cand", candidate_id)
        if not keys:
            match_result_cache_manager.delete_by_pattern(f"*{candidate_id}*")


_redis_cache = RedisCache(key_prefix="")
_memory_cache = MemoryCache(max_size=5000)

_llm_file_cache = FileCache(settings.UPLOADS_DIR / ".llm_cache")
_cv_file_cache = FileCache(settings.RESULTS_DIR)
_doc_cache_file_cache = FileCache(settings.UPLOADS_DIR / ".doc_cache")
_embedding_file_cache = FileCache(settings.UPLOADS_DIR / ".embed_cache")
_processing_job_file_cache = FileCache(settings.RESULTS_DIR / ".processing_jobs")

llm_cache_manager = CacheManager(
    namespace="llm_cache",
    providers=[_memory_cache, _redis_cache, _llm_file_cache],
    default_ttl=2592000,
)

cv_result_cache_manager = CacheManager(
    namespace="cv_result",
    providers=[_memory_cache, _redis_cache, _cv_file_cache],
    default_ttl=604800,
)

processing_job_cache_manager = CacheManager(
    namespace="processing_job",
    providers=[_memory_cache, _redis_cache, _processing_job_file_cache],
    default_ttl=settings.PROCESSING_JOB_TTL_SECONDS,
    persist_to_all_providers=True,
)

doc_cache_manager = CacheManager(
    namespace="doc_cache",
    providers=[_memory_cache, _redis_cache, _doc_cache_file_cache],
    default_ttl=2592000,
)

config_cache_manager = CacheManager(
    namespace="config",
    providers=[_memory_cache, _redis_cache],
    default_ttl=3600,
)

embedding_cache_manager = CacheManager(
    namespace="embed",
    providers=[_memory_cache, _redis_cache, _embedding_file_cache],
    default_ttl=2592000,
)

match_result_cache_manager = CacheManager(
    namespace="match_result",
    providers=[_memory_cache, _redis_cache],
    default_ttl=604800,
)

vacancy_cache_manager = CacheManager(
    namespace="vacancy",
    providers=[_memory_cache, _redis_cache],
    default_ttl=3600,
)

master_data_cache_manager = CacheManager(
    namespace="mst",
    providers=[_memory_cache, _redis_cache],
    default_ttl=3600,
)
