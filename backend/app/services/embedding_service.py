# backend/app/services/embedding_service.py
import hashlib
import math
import threading
import time
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

    _BATCH_SIZE = 10

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
            logger.info(
                f"[EMBEDDING] Cache HIT for model='{model}' hash='{content_hash[:12]}...' (0.0ms)"
            )
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
                logger.info(
                    f"[EMBEDDING] Generated embedding via Ollama model='{model}' hash='{content_hash[:12]}...' in {duration_ms:.1f}ms (cache miss)"
                )
                return embedding
            else:
                logger.warning(
                    f"[EMBEDDING] Ollama returned empty embedding for model='{model}' in {duration_ms:.1f}ms"
                )
                return None
        except Exception as exc:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            logger.warning(
                f"[EMBEDDING] Non-fatal embedding generation failure for model='{model}': {exc} ({duration_ms:.1f}ms)"
            )
            return None

    @classmethod
    def generate_batch_embeddings(
        cls,
        texts: list[str],
        model_version: str | None = None,
    ) -> dict[str, list[float]]:
        if not settings.EMBEDDING_ENABLED:
            return {}
        model = model_version or settings.EMBEDDING_MODEL
        result: dict[str, list[float]] = {}
        uncached: list[tuple[str, int]] = []

        for idx, text in enumerate(texts):
            content_hash = cls._content_hash(text)
            cache_key = cls._cache_key(content_hash, model)
            cached = embedding_cache_manager.get(cache_key)
            if cached is not None:
                result[str(idx)] = cached
            else:
                uncached.append((text, idx))

        if uncached:
            texts_to_fetch = [t for t, _ in uncached]
            embeddings = cls._call_ollama_batch_embed(model, texts_to_fetch)
            if embeddings is not None:
                for (text, idx), emb in zip(uncached, embeddings):
                    content_hash = cls._content_hash(text)
                    cache_key = cls._cache_key(content_hash, model)
                    embedding_cache_manager.set(cache_key, emb)
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
    def _call_ollama_batch_embed(
        cls, model: str, texts: list[str]
    ) -> list[list[float]] | None:
        if cls._is_model_throttled(model):
            return None

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), cls._BATCH_SIZE):
            batch = texts[i : i + cls._BATCH_SIZE]
            try:
                result = OllamaTransport.embed(model, batch)
                all_embeddings.extend(result.value)
                cls._failed_models_cache.pop(model, None)
            except OllamaModelUnavailableError:
                cls._failed_models_cache[model] = time.time()
                logger.error(f"[EMBEDDING CRITICAL] Model '{model}' not found in Ollama. Run: ollama pull {model}")
                break
            except OllamaUnavailableError:
                cls._failed_models_cache[model] = time.time()
                logger.error(f"[EMBEDDING CRITICAL] Ollama server is NOT running at {settings.OLLAMA_BASE_URL}.")
                break
            except OllamaError as exc:
                logger.warning(
                    f"[EMBEDDING] Ollama batch embed failed at offset {i} for model '{model}': "
                    f"{type(exc).__name__}; retrying the batch as individual inputs"
                )
                for text in batch:
                    single = cls._call_ollama_embed(model, text)
                    all_embeddings.append(single if single else [])
        return all_embeddings if len(all_embeddings) == len(texts) else None

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


def save_candidate_embedding(cv_key: str, embedding: list[float], content_hash: str | None = None) -> bool:
    """
    Upsert candidate embedding into PostgreSQL candidate_embeddings table keyed by cv_key.
    """
    from app.core.database import pg_SessionLocal

    if pg_SessionLocal is None:
        return False

    pg_db = pg_SessionLocal()
    try:
        from sqlalchemy import func
        from sqlalchemy.dialects.postgresql import insert

        from app.models.pg import CandidateEmbedding

        stmt = insert(CandidateEmbedding).values(
            cv_key=cv_key,
            embedding=embedding,
            embedding_model_version=settings.EMBEDDING_MODEL,
            content_hash=content_hash,
            updated_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["cv_key"],
            set_={
                "embedding": stmt.excluded.embedding,
                "embedding_model_version": stmt.excluded.embedding_model_version,
                "content_hash": stmt.excluded.content_hash,
                "updated_at": func.now(),
            },
        )
        pg_db.execute(stmt)
        pg_db.commit()
        # Also cache in L2/L3 cache manager under cv_key and content_hash
        cache_key = f"{settings.EMBEDDING_MODEL}:{cv_key}"
        embedding_cache_manager.set(cache_key, embedding)
        if content_hash and content_hash != cv_key:
            hash_cache_key = f"{settings.EMBEDDING_MODEL}:{content_hash}"
            embedding_cache_manager.set(hash_cache_key, embedding)
        return True
    except Exception as exc:
        pg_db.rollback()
        logger.error(f"save_candidate_embedding failed for cv_key={cv_key}: {exc}")
        return False
    finally:
        pg_db.close()


def get_candidate_embedding(cv_key: str) -> list[float] | None:
    """
    Retrieve candidate vector embedding by cv_key from PostgreSQL or cache.
    """
    from app.core.database import pg_SessionLocal

    if pg_SessionLocal is not None:
        pg_db = pg_SessionLocal()
        try:
            from app.models.pg import CandidateEmbedding

            rec = pg_db.query(CandidateEmbedding).filter(CandidateEmbedding.cv_key == cv_key).first()
            if rec and rec.embedding is not None:
                return [float(x) for x in list(rec.embedding)]
        except Exception as exc:
            logger.warning(f"get_candidate_embedding PG query error for cv_key={cv_key}: {exc}")
        finally:
            pg_db.close()

    cache_key = f"{settings.EMBEDDING_MODEL}:{cv_key}"
    cached = embedding_cache_manager.get(cache_key)
    if cached is not None:
        return cached
    return None


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


def save_vacancy_embedding(vacancy_id: int, embedding: list[float], content_hash: str | None = None) -> bool:
    """
    Upsert vacancy embedding into PostgreSQL vacancy_embeddings table keyed by vacancy_id.
    Also caches in embedding_cache_manager.
    """
    from app.core.database import pg_SessionLocal

    cache_key_id = f"{settings.EMBEDDING_MODEL}:vac_id:{vacancy_id}"
    embedding_cache_manager.set(cache_key_id, embedding)
    if content_hash:
        cache_key_hash = f"{settings.EMBEDDING_MODEL}:vac:{content_hash}"
        embedding_cache_manager.set(cache_key_hash, embedding)

    if pg_SessionLocal is None:
        return False

    pg_db = pg_SessionLocal()
    try:
        from sqlalchemy import func
        from sqlalchemy.dialects.postgresql import insert

        from app.models.pg import VacancyEmbedding

        stmt = insert(VacancyEmbedding).values(
            vacancy_id=vacancy_id,
            embedding=embedding,
            embedding_model_version=settings.EMBEDDING_MODEL,
            content_hash=content_hash,
            updated_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["vacancy_id"],
            set_={
                "embedding": stmt.excluded.embedding,
                "embedding_model_version": stmt.excluded.embedding_model_version,
                "content_hash": stmt.excluded.content_hash,
                "updated_at": func.now(),
            },
        )
        pg_db.execute(stmt)
        pg_db.commit()
        return True
    except Exception as exc:
        pg_db.rollback()
        logger.error(f"save_vacancy_embedding failed for vacancy_id={vacancy_id}: {exc}")
        return False
    finally:
        pg_db.close()


def get_vacancy_embedding(vacancy_id: int) -> tuple[list[float] | None, str | None]:
    """
    Retrieve vacancy vector embedding and content hash by vacancy_id from PostgreSQL or cache.
    """
    from app.core.database import pg_SessionLocal

    if pg_SessionLocal is not None:
        pg_db = pg_SessionLocal()
        try:
            from app.models.pg import VacancyEmbedding

            rec = pg_db.query(VacancyEmbedding).filter(VacancyEmbedding.vacancy_id == vacancy_id).first()
            if rec and rec.embedding is not None:
                vec = [float(x) for x in list(rec.embedding)]
                return vec, rec.content_hash
        except Exception as exc:
            logger.warning(f"get_vacancy_embedding PG query error for vacancy_id={vacancy_id}: {exc}")
        finally:
            pg_db.close()

    cache_key_id = f"{settings.EMBEDDING_MODEL}:vac_id:{vacancy_id}"
    cached = embedding_cache_manager.get(cache_key_id)
    if cached is not None:
        return cached, None
    return None, None

