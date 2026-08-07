from __future__ import annotations
# backend/app/services/embedding_service.py
import hashlib
import math
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.core.cache import embedding_cache_manager
from app.core.config import settings
from app.core.logging import logger
from app.services.ollama_transport import (
    OllamaError,
    OllamaModelUnavailableError,
    OllamaTimeoutError,
    OllamaTransport,
    OllamaUnavailableError,
)


class EmbeddingSchemaError(Exception):
    """Raised when PostgreSQL embedding table schema is invalid or missing required columns."""
    pass


class EmbeddingDatabaseConnectionError(Exception):
    """Raised when PostgreSQL database connection is unavailable or unreachable."""
    pass


class EmbeddingCacheStatus(str, Enum):
    CACHE_HIT = "CACHE_HIT"
    CACHE_MISS = "CACHE_MISS"
    STALE_CACHE = "STALE_CACHE"



def _normalize_watermark(val: Any) -> str | None:
    if not val:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            val = val.replace(tzinfo=timezone.utc)
        else:
            val = val.astimezone(timezone.utc)
        return val.strftime("%Y-%m-%d %H:%M:%S")
    try:
        from dateutil.parser import parse
        dt = parse(str(val))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(val).strip()



def get_embedding(text: str, model_name: str | None = None) -> list[float]:
    """
    Generate vector embedding for given text using Ollama /api/embed endpoint.
    Normalized to delegate through EmbeddingService for caching and connection reuse.
    """
    emb = EmbeddingService.generate_embedding(text, model_version=model_name)
    if emb is not None:
        return emb

    # If embedding generation returned None (e.g., service unavailable or model error), raise RuntimeError or return empty list
    model = model_name or settings.EMBEDDING_MODEL
    logger.error(f"[EMBEDDING CRITICAL] Failed to generate embedding for model '{model}'.")
    raise RuntimeError(f"Failed to generate embedding for model '{model}'. Check Ollama service availability.")


class EmbeddingService:
    """
    Generates text embeddings via the shared Ollama transport with Redis L2 + File L3 caching.
    Cache key = ``embed:{model_version}:{sha256(text)}``.
    Supports thread-safe metrics, timing instrumentation, and detailed logging.
    """

    _metrics_lock = threading.Lock()
    _total_requests: int = 0
    _cache_hits: int = 0
    _cache_misses: int = 0
    _last_processing_time_ms: float = 0.0
    _total_processing_time_ms: float = 0.0

    # Store timestamp of when a model failed to prevent log flooding
    _failed_models_cache: dict[str, float] = {}

    @classmethod
    def get_metrics(cls) -> dict[str, Any]:
        """
        Return runtime metrics for embedding generation.
        """
        with cls._metrics_lock:
            total = cls._total_requests
            hits = cls._cache_hits
            misses = cls._cache_misses
            rate = round((hits / total) * 100.0, 2) if total > 0 else 0.0
            return {
                "total_requests": total,
                "cache_hits": hits,
                "cache_misses": misses,
                "cache_hit_rate_pct": rate,
                "last_processing_time_ms": round(cls._last_processing_time_ms, 2),
                "total_processing_time_ms": round(cls._total_processing_time_ms, 2),
                "embedding_model": settings.EMBEDDING_MODEL,
            }

    @classmethod
    def reset_metrics(cls) -> None:
        """
        Reset runtime metrics.
        """
        with cls._metrics_lock:
            cls._total_requests = 0
            cls._cache_hits = 0
            cls._cache_misses = 0
            cls._last_processing_time_ms = 0.0
            cls._total_processing_time_ms = 0.0

    @classmethod
    def get_embedding(cls, text: str, model_version: str | None = None) -> list[float]:
        return get_embedding(text, model_name=model_version)

    @classmethod
    def _content_hash(cls, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @classmethod
    def _cache_key(cls, content_hash: str, model_version: str) -> str:
        return f"{model_version}:{content_hash}"

    @classmethod
    def generate_embedding(
        cls,
        text: str,
        model_version: str | None = None,
        identifier: str | None = None,
    ) -> list[float] | None:
        if not settings.EMBEDDING_ENABLED:
            return None

        model = model_version or settings.EMBEDDING_MODEL
        content_hash = cls._content_hash(text)
        primary_cache_key = cls._cache_key(content_hash, model)
        id_cache_key = cls._cache_key(identifier, model) if identifier else None

        with cls._metrics_lock:
            cls._total_requests += 1

        # Check primary content-hash key first, then alias identifier key
        cached = embedding_cache_manager.get(primary_cache_key)
        if cached is None and id_cache_key:
            cached = embedding_cache_manager.get(id_cache_key)

        if cached is not None:
            with cls._metrics_lock:
                cls._cache_hits += 1
            logger.info(f"[EMBEDDING] Cache HIT for model='{model}' hash='{content_hash[:12]}...' (0.0ms)")
            return cached

        with cls._metrics_lock:
            cls._cache_misses += 1

        t0 = time.perf_counter()
        try:
            embedding = cls._call_ollama_embed(model, text)
            duration_ms = (time.perf_counter() - t0) * 1000.0

            with cls._metrics_lock:
                cls._last_processing_time_ms = duration_ms
                cls._total_processing_time_ms += duration_ms

            if embedding is not None:
                embedding_cache_manager.set(primary_cache_key, embedding)
                if id_cache_key and id_cache_key != primary_cache_key:
                    embedding_cache_manager.set(id_cache_key, embedding)
                logger.info(f"[EMBEDDING] Generated embedding via Ollama model='{model}' hash='{content_hash[:12]}...' in {duration_ms:.1f}ms (cache miss)")
                return embedding
            else:
                logger.warning(f"[EMBEDDING] Ollama returned empty embedding for model='{model}' in {duration_ms:.1f}ms")
                return None
        except Exception as exc:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            logger.warning(f"[EMBEDDING] Non-fatal embedding generation failure for model='{model}': {exc} ({duration_ms:.1f}ms)")
            return None

    @classmethod
    def generate_batch_embeddings(
        cls,
        texts: list[str],
        model_version: str | None = None,
        identifiers: list[str | None] | None = None,
    ) -> dict[str, list[float]]:
        if not settings.EMBEDDING_ENABLED:
            return {}
        if identifiers is not None and len(identifiers) != len(texts):
            raise ValueError("Embedding identifiers must match the number of texts.")
        model = model_version or settings.EMBEDDING_MODEL
        result: dict[str, list[float]] = {}
        uncached: list[tuple[str, int, str | None]] = []

        for idx, text in enumerate(texts):
            if not text or not text.strip():
                continue
            identifier = identifiers[idx] if identifiers is not None else None
            content_hash = cls._content_hash(text)
            cache_key = cls._cache_key(content_hash, model)
            cached = embedding_cache_manager.get(cache_key)
            if cached is None and identifier:
                cached = embedding_cache_manager.get(cls._cache_key(identifier, model))
            if cached is not None:
                result[str(idx)] = cached
            else:
                uncached.append((text, idx, identifier))

        if uncached:
            texts_to_fetch = [text for text, _, _ in uncached]
            embeddings = cls._call_ollama_batch_embed(model, texts_to_fetch)
            if embeddings is not None:
                for (text, idx, identifier), emb in zip(uncached, embeddings):
                    content_hash = cls._content_hash(text)
                    cache_key = cls._cache_key(content_hash, model)
                    embedding_cache_manager.set(cache_key, emb)
                    if identifier:
                        embedding_cache_manager.set(cls._cache_key(identifier, model), emb)
                    result[str(idx)] = emb
        return result

    @classmethod
    def _is_model_throttled(cls, model: str) -> bool:
        """Check if model failed recently (within 60 seconds)."""
        last_failure = cls._failed_models_cache.get(model)
        return bool(last_failure and time.time() - last_failure < 60)

    @classmethod
    def _call_ollama_embed(cls, model: str, text: str) -> list[float] | None:
        if cls._is_model_throttled(model):
            return None

        try:
            result = OllamaTransport.embed(model, [text])
            cls._failed_models_cache.pop(model, None)
            return result.value[0]
        except OllamaModelUnavailableError:
            cls._failed_models_cache[model] = time.time()
            logger.error(f"[EMBEDDING CRITICAL] Model '{model}' not found in Ollama. Run: ollama pull {model}")
            return None
        except OllamaTimeoutError:
            logger.warning(f"[EMBEDDING] Timeout calling Ollama for model '{model}'")
            return None
        except OllamaUnavailableError:
            cls._failed_models_cache[model] = time.time()
            logger.error(f"[EMBEDDING CRITICAL] Ollama server is NOT running at {settings.OLLAMA_BASE_URL}.")
            return None
        except OllamaError as exc:
            logger.warning(f"[EMBEDDING] Ollama embed call failed for model '{model}': {type(exc).__name__}")
            return None

    @classmethod
    def _call_ollama_batch_embed(cls, model: str, texts: list[str]) -> list[list[float]] | None:
        if cls._is_model_throttled(model):
            return None

        try:
            result = OllamaTransport.embed(model, texts)
            cls._failed_models_cache.pop(model, None)
            return result.value
        except OllamaModelUnavailableError:
            cls._failed_models_cache[model] = time.time()
            logger.error(f"[EMBEDDING CRITICAL] Model '{model}' not found in Ollama. Run: ollama pull {model}")
            return None
        except OllamaTimeoutError:
            logger.warning(f"[EMBEDDING] Batch timeout calling Ollama for model '{model}'")
            return None
        except OllamaUnavailableError:
            cls._failed_models_cache[model] = time.time()
            logger.error(f"[EMBEDDING CRITICAL] Ollama server is NOT running at {settings.OLLAMA_BASE_URL}.")
            return None
        except OllamaError as exc:
            logger.warning(f"[EMBEDDING] Ollama batch embed failed for model '{model}': {type(exc).__name__}; no per-item retry was attempted")
            return None

    @classmethod
    def cosine_similarity(cls, a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(av * bv for av, bv in zip(a, b))
        norm_a = math.sqrt(sum(av * av for av in a))
        norm_b = math.sqrt(sum(bv * bv for bv in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)


def save_candidate_embedding(
    cv_key: str,
    embedding: list[float],
    content_hash: str | None = None,
    source_snapshot: str | None = None,
    source_watermark: Any = None,
    freshness_status: str = "FRESH",
) -> bool:
    """
    Upsert candidate embedding into PostgreSQL candidate_embeddings table keyed by cv_key.
    Guarantees PostgreSQL commit succeeds BEFORE updating L2/L3 cache.
    On DB failure: invokes pg_db.rollback() and re-raises exception (never populates cache).
    """
    from app.core.database import PostgresAppSession

    if PostgresAppSession is None:
        raise EmbeddingDatabaseConnectionError("PostgresAppSession is None.")

    pg_db = PostgresAppSession()
    try:
        from sqlalchemy import func
        from sqlalchemy.dialects.postgresql import insert

        from app.models.pg import CandidateEmbedding

        stmt = insert(CandidateEmbedding).values(
            cv_key=cv_key,
            embedding=embedding,
            embedding_model_version=settings.EMBEDDING_MODEL,
            content_hash=content_hash,
            source_snapshot=source_snapshot,
            source_watermark=source_watermark,
            freshness_status=freshness_status,
            updated_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["cv_key"],
            set_={
                "embedding": stmt.excluded.embedding,
                "embedding_model_version": stmt.excluded.embedding_model_version,
                "content_hash": stmt.excluded.content_hash,
                "source_snapshot": stmt.excluded.source_snapshot,
                "source_watermark": stmt.excluded.source_watermark,
                "freshness_status": stmt.excluded.freshness_status,
                "updated_at": func.now(),
            },
        )
        pg_db.execute(stmt)
        pg_db.commit()

        # ONLY AFTER successful DB commit, update L2/L3 cache
        cache_key = f"{settings.EMBEDDING_MODEL}:{cv_key}"
        embedding_cache_manager.set(cache_key, embedding)
        if content_hash and content_hash != cv_key:
            hash_cache_key = f"{settings.EMBEDDING_MODEL}:{content_hash}"
            embedding_cache_manager.set(hash_cache_key, embedding)
        return True
    except Exception as exc:
        pg_db.rollback()
        logger.error(f"save_candidate_embedding failed for cv_key={cv_key}: {exc}")
        orig = getattr(exc, "orig", exc)
        pgcode = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None)
        if pgcode in ("42703", "42P01") or "UndefinedColumn" in str(exc) or "UndefinedTable" in str(exc):
            raise EmbeddingSchemaError(f"save_candidate_embedding schema error: {exc}") from exc
        raise
    finally:
        pg_db.close()


def get_candidate_embedding_with_status(
    cv_key: str,
    current_content_hash: str | None = None,
    current_watermark: Any = None,
) -> tuple[list[float] | None, EmbeddingCacheStatus]:
    """
    Retrieve candidate vector embedding and cache status by cv_key.
    PostgreSQL is the single source of truth.
    """
    from app.core.database import PostgresAppSession
    from app.models.pg import CandidateEmbedding

    cache_key = f"{settings.EMBEDDING_MODEL}:{cv_key}"

    if PostgresAppSession is None:
        logger.error("[EMBEDDING_CACHE] PostgresAppSession is None (DB_CONNECTION_ERROR)")
        raise EmbeddingDatabaseConnectionError("PostgreSQL database session is not configured.")

    pg_db = PostgresAppSession()
    try:
        rec = pg_db.query(CandidateEmbedding).filter(CandidateEmbedding.cv_key == cv_key).first()

        if rec is None:
            # PG row missing -> evict any orphan L2/L3 cache entry -> CACHE_MISS
            embedding_cache_manager.delete(cache_key)
            return None, EmbeddingCacheStatus.CACHE_MISS

        # PG row exists -> evaluate freshness & content matching
        is_stale = rec.freshness_status == "STALE" or rec.embedding is None

        # Primary check: content_hash
        if current_content_hash and rec.content_hash and rec.content_hash != current_content_hash:
            is_stale = True

        # Secondary check: source_watermark (normalized)
        if current_watermark and rec.source_watermark:
            w_norm_current = _normalize_watermark(current_watermark)
            w_norm_rec = _normalize_watermark(rec.source_watermark)
            if w_norm_current and w_norm_rec and w_norm_current != w_norm_rec:
                is_stale = True

        if is_stale:
            # Evict L2/L3 cache before returning STALE_CACHE
            embedding_cache_manager.delete(cache_key)
            logger.info(f"[EMBEDDING_CACHE] STALE_CACHE for cv_key='{cv_key}' (evicted cache).")
            return None, EmbeddingCacheStatus.STALE_CACHE

        # PG row is FRESH & matching
        vec = [float(x) for x in list(rec.embedding)]
        embedding_cache_manager.set(cache_key, vec)
        return vec, EmbeddingCacheStatus.CACHE_HIT

    except (EmbeddingSchemaError, EmbeddingDatabaseConnectionError):
        raise
    except Exception as exc:
        orig = getattr(exc, "orig", exc)
        pgcode = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None)

        if pgcode in ("42703", "42P01") or "UndefinedColumn" in str(exc) or "UndefinedTable" in str(exc):
            logger.critical(f"[DB_SCHEMA_ERROR] CandidateEmbedding table schema error (SQLSTATE {pgcode}): {exc}")
            raise EmbeddingSchemaError(f"PostgreSQL candidate_embeddings schema error (SQLSTATE {pgcode}): {exc}") from exc

        if pgcode in ("08001", "08006", "08003") or "connection" in str(exc).lower():
            logger.error(f"[DB_CONNECTION_ERROR] PostgreSQL connection failure (SQLSTATE {pgcode}): {exc}")
            raise EmbeddingDatabaseConnectionError(f"PostgreSQL database connection failure: {exc}") from exc

        logger.error(f"[EMBEDDING_CACHE] Unexpected database query failure for cv_key='{cv_key}': {exc}")
        raise
    finally:
        pg_db.close()


def get_candidate_embedding(cv_key: str) -> list[float] | None:
    """
    Retrieve candidate vector embedding by cv_key from PostgreSQL or cache.
    """
    emb, _ = get_candidate_embedding_with_status(cv_key)
    return emb



def build_vacancy_canonical_text(job: dict[str, Any]) -> str:
    """
    Construct semantic canonical embedding input from all active vacancy fields:
    Vacancy Title, Job Description, Required Skills, Experience, Education,
    Certifications, Department, and Responsibilities.
    """
    parts: list[str] = []

    title = job.get("title") or ""
    if title:
        parts.append(f"Vacancy Title: {title}")

    dept = job.get("department_name") or job.get("department") or ""
    if dept:
        parts.append(f"Department: {dept}")

    comp = job.get("company_name") or ""
    if comp:
        parts.append(f"Company: {comp}")

    desc = job.get("job_description") or job.get("description") or job.get("JobProfileDesc") or ""
    if desc:
        parts.append(f"Job Description: {desc}")

    resp = job.get("responsibilities") or ""
    if resp and resp != desc:
        parts.append(f"Responsibilities: {resp}")

    skills = job.get("required_skills") or []
    if skills:
        skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)
        parts.append(f"Required Skills: {skills_str}")

    pref = job.get("preferred_keywords") or []
    if pref and pref != skills:
        pref_str = ", ".join(pref) if isinstance(pref, list) else str(pref)
        parts.append(f"Preferred Keywords: {pref_str}")

    min_exp = job.get("min_experience_years")
    max_exp = job.get("max_experience_years")
    if min_exp is not None or max_exp is not None:
        min_str = f"{min_exp}" if min_exp is not None else "0"
        max_str = f"{max_exp}" if max_exp is not None else "N/A"
        parts.append(f"Experience Required: {min_str} to {max_str} years")

    edu = job.get("education") or job.get("education_requirements") or ""
    if edu:
        parts.append(f"Education Requirements: {edu}")

    certs = job.get("certifications") or ""
    if certs:
        parts.append(f"Certifications: {certs}")

    return "\n".join(parts).strip()


def save_vacancy_embedding(
    vacancy_id: int,
    embedding: list[float],
    content_hash: str | None = None,
    source_snapshot: str | None = None,
    source_watermark: Any = None,
    freshness_status: str = "FRESH",
) -> bool:
    """
    Upsert vacancy embedding into PostgreSQL vacancy_embeddings table keyed by vacancy_id.
    Guarantees PostgreSQL commit succeeds BEFORE updating L2/L3 cache.
    On DB failure: invokes pg_db.rollback() and re-raises exception (never populates cache).
    """
    from app.core.database import PostgresAppSession

    if PostgresAppSession is None:
        raise EmbeddingDatabaseConnectionError("PostgresAppSession is None.")

    pg_db = PostgresAppSession()
    try:
        from sqlalchemy import func
        from sqlalchemy.dialects.postgresql import insert

        from app.models.pg import VacancyEmbedding

        stmt = insert(VacancyEmbedding).values(
            vacancy_id=vacancy_id,
            embedding=embedding,
            embedding_model_version=settings.EMBEDDING_MODEL,
            content_hash=content_hash,
            source_snapshot=source_snapshot,
            source_watermark=source_watermark,
            freshness_status=freshness_status,
            updated_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["vacancy_id"],
            set_={
                "embedding": stmt.excluded.embedding,
                "embedding_model_version": stmt.excluded.embedding_model_version,
                "content_hash": stmt.excluded.content_hash,
                "source_snapshot": stmt.excluded.source_snapshot,
                "source_watermark": stmt.excluded.source_watermark,
                "freshness_status": stmt.excluded.freshness_status,
                "updated_at": func.now(),
            },
        )
        pg_db.execute(stmt)
        pg_db.commit()

        # ONLY AFTER successful DB commit, update L2/L3 cache
        cache_key_id = f"{settings.EMBEDDING_MODEL}:vac_id:{vacancy_id}"
        embedding_cache_manager.set(cache_key_id, embedding)
        if content_hash:
            cache_key_hash = f"{settings.EMBEDDING_MODEL}:vac:{content_hash}"
            embedding_cache_manager.set(cache_key_hash, embedding)
        return True
    except Exception as exc:
        pg_db.rollback()
        logger.error(f"save_vacancy_embedding failed for vacancy_id={vacancy_id}: {exc}")
        orig = getattr(exc, "orig", exc)
        pgcode = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None)
        if pgcode in ("42703", "42P01") or "UndefinedColumn" in str(exc) or "UndefinedTable" in str(exc):
            raise EmbeddingSchemaError(f"save_vacancy_embedding schema error: {exc}") from exc
        raise
    finally:
        pg_db.close()


def get_vacancy_embedding_with_status(
    vacancy_id: int,
    current_content_hash: str | None = None,
    current_watermark: Any = None,
) -> tuple[list[float] | None, str | None, EmbeddingCacheStatus]:
    """
    Retrieve vacancy vector embedding, content hash, and cache status by vacancy_id from PostgreSQL.
    PostgreSQL is the single source of truth.
    """
    from app.core.database import PostgresAppSession
    from app.models.pg import VacancyEmbedding

    cache_key_id = f"{settings.EMBEDDING_MODEL}:vac_id:{vacancy_id}"

    if PostgresAppSession is None:
        logger.error("[EMBEDDING_CACHE] PostgresAppSession is None for get_vacancy_embedding")
        raise EmbeddingDatabaseConnectionError("PostgreSQL database session is not configured.")

    pg_db = PostgresAppSession()
    try:
        rec = pg_db.query(VacancyEmbedding).filter(VacancyEmbedding.vacancy_id == vacancy_id).first()

        if rec is None:
            # PG row missing -> evict any orphan L2/L3 cache entry -> CACHE_MISS
            embedding_cache_manager.delete(cache_key_id)
            return None, None, EmbeddingCacheStatus.CACHE_MISS

        is_stale = rec.freshness_status == "STALE" or rec.embedding is None

        # Primary check: content_hash
        if current_content_hash and rec.content_hash and rec.content_hash != current_content_hash:
            is_stale = True

        # Secondary check: source_watermark (normalized)
        if current_watermark and rec.source_watermark:
            w_norm_current = _normalize_watermark(current_watermark)
            w_norm_rec = _normalize_watermark(rec.source_watermark)
            if w_norm_current and w_norm_rec and w_norm_current != w_norm_rec:
                is_stale = True

        if is_stale:
            embedding_cache_manager.delete(cache_key_id)
            logger.info(f"[EMBEDDING_CACHE] STALE_CACHE for vacancy_id={vacancy_id} (evicted cache).")
            return None, rec.content_hash, EmbeddingCacheStatus.STALE_CACHE

        vec = [float(x) for x in list(rec.embedding)]
        embedding_cache_manager.set(cache_key_id, vec)
        return vec, rec.content_hash, EmbeddingCacheStatus.CACHE_HIT

    except (EmbeddingSchemaError, EmbeddingDatabaseConnectionError):
        raise
    except Exception as exc:
        orig = getattr(exc, "orig", exc)
        pgcode = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None)

        if pgcode in ("42703", "42P01") or "UndefinedColumn" in str(exc) or "UndefinedTable" in str(exc):
            logger.critical(f"[DB_SCHEMA_ERROR] VacancyEmbedding table schema error (SQLSTATE {pgcode}): {exc}")
            raise EmbeddingSchemaError(f"PostgreSQL vacancy_embeddings schema error (SQLSTATE {pgcode}): {exc}") from exc

        if pgcode in ("08001", "08006", "08003") or "connection" in str(exc).lower():
            logger.error(f"[DB_CONNECTION_ERROR] PostgreSQL connection failure (SQLSTATE {pgcode}): {exc}")
            raise EmbeddingDatabaseConnectionError(f"PostgreSQL database connection failure: {exc}") from exc

        logger.error(f"[EMBEDDING_CACHE] Unexpected database query failure for vacancy_id={vacancy_id}: {exc}")
        raise
    finally:
        pg_db.close()


def get_vacancy_embedding(vacancy_id: int) -> tuple[list[float] | None, str | None]:
    """
    Retrieve vacancy vector embedding and content hash by vacancy_id from PostgreSQL or cache.
    """
    vec, content_hash, _ = get_vacancy_embedding_with_status(vacancy_id)
    return vec, content_hash

def get_candidate_embedding_metadata(cv_key: str) -> dict | None:
    from app.core.database import PostgresAppSession
    from app.models.pg import CandidateEmbedding

    if PostgresAppSession is None:
        return None

    pg_db = PostgresAppSession()
    try:
        record = pg_db.query(CandidateEmbedding).filter(CandidateEmbedding.cv_key == cv_key).first()
        if record:
            return {
                "source_watermark": record.source_watermark,
                "freshness_status": record.freshness_status,
                "content_hash": record.content_hash,
            }
        return None
    except Exception as exc:
        orig = getattr(exc, "orig", exc)
        pgcode = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None)
        if pgcode in ("42703", "42P01") or "UndefinedColumn" in str(exc) or "UndefinedTable" in str(exc):
            raise EmbeddingSchemaError(f"get_candidate_embedding_metadata schema error: {exc}") from exc
        raise
    finally:
        pg_db.close()


def get_vacancy_embedding_metadata(vacancy_id: int) -> dict | None:
    from app.core.database import PostgresAppSession
    from app.models.pg import VacancyEmbedding
    
    if PostgresAppSession is None:
        return None
        
    pg_db = PostgresAppSession()
    try:
        record = pg_db.query(VacancyEmbedding).filter(VacancyEmbedding.vacancy_id == vacancy_id).first()
        if record:
            return {
                "source_watermark": record.source_watermark,
                "freshness_status": record.freshness_status,
                "content_hash": record.content_hash
            }
        return None
    except Exception as exc:
        orig = getattr(exc, "orig", exc)
        pgcode = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None)
        if pgcode in ("42703", "42P01") or "UndefinedColumn" in str(exc) or "UndefinedTable" in str(exc):
            raise EmbeddingSchemaError(f"get_vacancy_embedding_metadata schema error: {exc}") from exc
        raise
    finally:
        pg_db.close()
