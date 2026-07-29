import hashlib
import json
import math
from typing import Any

import httpx

from app.core.cache import embedding_cache_manager
from app.core.config import settings
from app.core.logging import logger


def get_embedding(text: str, model_name: str | None = None) -> list[float]:
    """
    Generate vector embedding for given text using Ollama /api/embeddings endpoint with nomic-embed-text.
    """
    model = model_name or settings.EMBEDDING_MODEL
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embeddings"
    payload = {"model": model, "prompt": text}
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            embedding = data.get("embedding")
            if embedding and isinstance(embedding, list):
                return embedding
            # Fallback to /api/embed if /api/embeddings didn't return 'embedding' key
            embed_url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embed"
            resp2 = client.post(embed_url, json={"model": model, "input": text})
            resp2.raise_for_status()
            data2 = resp2.json()
            embs = data2.get("embeddings")
            if embs and len(embs) > 0:
                return embs[0]
            raise ValueError(f"Empty embedding returned for model {model}")
    except Exception as exc:
        logger.error(f"get_embedding failed for text '{text[:40]}...': {exc}")
        raise exc


class EmbeddingService:
    """
    Generates text embeddings via Ollama /api/embed or /api/embeddings with Redis L2 + File L3 caching.
    Cache key = ``embed:{model_version}:{sha256(text)}``.
    """

    _BATCH_SIZE = 10

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
        content_hash = identifier or cls._content_hash(text)
        cache_key = cls._cache_key(content_hash, model)

        cached = embedding_cache_manager.get(cache_key)
        if cached is not None:
            return cached

        try:
            embedding = cls._call_ollama_embed(model, text)
            if embedding is not None:
                embedding_cache_manager.set(cache_key, embedding)
            return embedding
        except Exception:
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
    def _call_ollama_embed(cls, model: str, text: str) -> list[float] | None:
        try:
            return get_embedding(text, model_name=model)
        except Exception as exc:
            logger.warning(f"Embedding generation failed for model {model}: {exc}")
            return None

    @classmethod
    def _call_ollama_batch_embed(
        cls, model: str, texts: list[str]
    ) -> list[list[float]] | None:
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embed"
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), cls._BATCH_SIZE):
            batch = texts[i : i + cls._BATCH_SIZE]
            try:
                with httpx.Client(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
                    resp = client.post(url, json={"model": model, "input": batch})
                    resp.raise_for_status()
                    data = resp.json()
                    batch_embs = data.get("embeddings")
                    if batch_embs and len(batch_embs) == len(batch):
                        all_embeddings.extend(batch_embs)
                    else:
                        logger.warning(
                            f"Ollama batch embed returned {len(batch_embs or [])} embeddings for {len(batch)} texts"
                        )
                        for text in batch:
                            single = cls._call_ollama_embed(model, text)
                            all_embeddings.append(single if single else [])
            except Exception as exc:
                logger.warning(f"Ollama batch embed failed at offset {i}: {exc}")
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
        # Also cache in L2/L3 cache manager under cv_key
        cache_key = f"{settings.EMBEDDING_MODEL}:{cv_key}"
        embedding_cache_manager.set(cache_key, embedding)
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


