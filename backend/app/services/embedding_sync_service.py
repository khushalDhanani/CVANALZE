# backend/app/services/embedding_sync_service.py
import hashlib
from typing import Any

from app.core.config import settings
from app.core.logging import logger


class EmbeddingSyncService:
    """
    Dedicated service for generating, checking content hashes, and persisting
    semantic vacancy vector embeddings to PostgreSQL pgvector and cache manager.
    """

    @classmethod
    def sync_vacancy_embeddings(cls, job_dicts: list[dict[str, Any]]) -> dict[str, int]:
        """
        Generates and caches semantic vector embeddings for all active vacancies.
        Uses rich canonical text, checks content hashes for incremental updates,
        and persists embeddings to PostgreSQL and cache manager. Returns explicit
        sync metrics for operational callers.
        """
        metrics = {"total": len(job_dicts), "synced": 0, "skipped": 0, "failed": 0}
        if not settings.EMBEDDING_ENABLED:
            metrics["skipped"] = metrics["total"]
            return metrics

        from app.core.cache import embedding_cache_manager as _ecm
        from app.services.embedding_service import (
            EmbeddingService as _es,
        )
        from app.services.embedding_service import (
            build_vacancy_canonical_text,
            get_vacancy_embedding,
            save_vacancy_embedding,
        )

        model = settings.EMBEDDING_MODEL
        uncached: list[tuple[int, dict[str, Any], str, str]] = []  # (vac_id, job, canonical_text, content_hash)

        for job in job_dicts:
            vac_id = job.get("vacancy_id") or job.get("id")
            try:
                vac_id_int = int(vac_id) if vac_id is not None else 0
            except (ValueError, TypeError):
                vac_id_int = 0

            canonical_text = build_vacancy_canonical_text(job)
            if not canonical_text:
                continue

            content_hash = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()
            job["_canonical_text"] = canonical_text
            job["_content_hash"] = content_hash

            # Check if embedding already exists in cache or DB for this model and content hash
            cached_emb = _ecm.get(f"{model}:vac:{content_hash}")
            if cached_emb is None and vac_id_int > 0:
                pg_emb, stored_hash = get_vacancy_embedding(vac_id_int)
                if pg_emb is not None and stored_hash == content_hash:
                    cached_emb = pg_emb
                    _ecm.set(f"{model}:vac:{content_hash}", cached_emb)

            if cached_emb is None:
                uncached.append((vac_id_int, job, canonical_text, content_hash))

        if uncached:
            uncached_texts = [item[2] for item in uncached]
            embeddings = _es.generate_batch_embeddings(uncached_texts, model_version=model)
            if len(embeddings) == len(uncached):
                for index, (vac_id_int, job, _, content_hash) in enumerate(uncached):
                    emb = embeddings.get(str(index))
                    if emb:
                        _ecm.set(f"{model}:vac:{content_hash}", emb)
                        if vac_id_int > 0:
                            save_vacancy_embedding(vac_id_int, emb, content_hash)
                        metrics["synced"] += 1
                    else:
                        metrics["failed"] += 1
            else:
                metrics["failed"] = len(uncached)

        metrics["skipped"] = metrics["total"] - len(uncached)

        logger.info(f"[EMBEDDING_SYNC] Processed {len(job_dicts)} vacancies: {metrics['synced']} newly embedded, {metrics['skipped']} cached/unchanged, {metrics['failed']} failed.")
        return metrics
