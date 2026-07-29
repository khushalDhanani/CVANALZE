import hashlib
import json
import math
from typing import Any

import httpx

from app.core.cache import embedding_cache_manager
from app.core.config import settings
from app.core.logging import logger


class EmbeddingService:
    """
    Generates text embeddings via Ollama /api/embed with Redis L2 + File L3 caching.
    Cache key = ``embed:{model_version}:{sha256(text)}``.
    """

    _BATCH_SIZE = 10

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

        embedding = cls._call_ollama_embed(model, text)
        if embedding is not None:
            embedding_cache_manager.set(cache_key, embedding)
        return embedding

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
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embed"
        try:
            with httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
                resp = client.post(url, json={"model": model, "input": text})
                resp.raise_for_status()
                data = resp.json()
                embeddings = data.get("embeddings")
                if embeddings and len(embeddings) > 0:
                    return embeddings[0]
                logger.warning(f"Ollama embed returned empty embeddings for model {model}")
                return None
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
