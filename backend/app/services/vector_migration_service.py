import hashlib
from typing import Any

from sqlalchemy import func, select

from app.core.config import settings
from app.core.logging import logger
from app.repositories.job import JobRepository
from app.repositories.result import ResultRepository
from app.services.embedding_service import (
    EmbeddingService,
    get_candidate_embedding,
    save_candidate_embedding,
)


class VectorDatabaseMigrationService:
    """
    Service for migrating, background indexing, and synchronizing candidate & vacancy embeddings
    into PostgreSQL pgvector database with HNSW indexes, content-hash incremental updates,
    model version tracking, and multi-tier fallback.
    """

    @classmethod
    def sync_candidate_embeddings(cls) -> dict[str, int]:
        """
        Scan all candidate results and asynchronously populate missing candidate embeddings into pgvector DB.
        Returns sync metrics dict: {"total": X, "synced": Y, "skipped": Z, "failed": F}.
        """
        results = ResultRepository.list_all_results()
        metrics = {"total": len(results), "synced": 0, "skipped": 0, "failed": 0}

        model_version = settings.EMBEDDING_MODEL

        for r in results:
            if not r or not isinstance(r, dict):
                continue

            cv_key = str(r.get("id") or r.get("filename") or "")
            cv_key = cv_key.removesuffix(".json")

            markdown_text = str(r.get("markdown") or r.get("text") or "")
            if not markdown_text.strip():
                metrics["skipped"] += 1
                continue

            cv_hash = str(r.get("cv_hash") or hashlib.sha256(markdown_text.encode("utf-8")).hexdigest())

            # Check if embedding exists in PostgreSQL / cache
            existing_emb = get_candidate_embedding(cv_key)
            if existing_emb is not None:
                metrics["skipped"] += 1
                continue

            try:
                new_emb = EmbeddingService.generate_embedding(markdown_text, model_version=model_version, identifier=cv_key)
                if new_emb:
                    save_candidate_embedding(cv_key, new_emb, cv_hash)
                    metrics["synced"] += 1
                else:
                    metrics["failed"] += 1
            except Exception as exc:
                logger.warning(f"[VECTOR_SYNC] Failed embedding candidate '{cv_key}': {exc}")
                metrics["failed"] += 1

        logger.info(f"[VECTOR_SYNC] Candidate embedding sync complete: {metrics['synced']} synced, {metrics['skipped']} skipped/unchanged, {metrics['failed']} failed.")
        return metrics

    @classmethod
    def sync_vacancy_embeddings(cls) -> dict[str, int]:
        """
        Scan all active vacancies and populate missing vacancy embeddings into pgvector DB & cache.
        """
        jobs = JobRepository.get_all_jobs()
        if not jobs:
            return {"total": 0, "synced": 0, "skipped": 0, "failed": 0}

        total = len(jobs)
        sync_metrics = JobRepository._cache_vacancy_embeddings(jobs)
        if not isinstance(sync_metrics, dict):
            logger.warning("[VECTOR_SYNC] Vacancy embedding helper returned no metrics; using the legacy all-skipped compatibility result.")
            sync_metrics = {"total": total, "synced": 0, "skipped": total, "failed": 0}

        metrics = {
            "total": total,
            "synced": max(0, int(sync_metrics.get("synced", 0))),
            "skipped": max(0, int(sync_metrics.get("skipped", 0))),
            "failed": max(0, int(sync_metrics.get("failed", 0))),
        }

        logger.info(f"[VECTOR_SYNC] Vacancy embedding sync complete: {metrics['synced']} newly embedded, {metrics['skipped']} cached/unchanged, {metrics['failed']} failed.")
        return metrics

    @classmethod
    def sync_all_embeddings(cls) -> dict[str, Any]:
        """
        Synchronize both candidate and vacancy embeddings into PostgreSQL pgvector.
        """
        cand_metrics = cls.sync_candidate_embeddings()
        vac_metrics = cls.sync_vacancy_embeddings()
        return {
            "status": "completed",
            "model_version": settings.EMBEDDING_MODEL,
            "candidate_embeddings": cand_metrics,
            "vacancy_embeddings": vac_metrics,
        }

    @classmethod
    def run_sync_safely(cls) -> None:
        """Run an acknowledged background sync without leaking failures into the ASGI response lifecycle."""
        try:
            result = cls.sync_all_embeddings()
            logger.info(f"[VECTOR_SYNC] Background synchronization finished with status='{result.get('status', 'unknown')}'.")
        except Exception as exc:
            logger.exception(f"[VECTOR_SYNC] Background synchronization failed: {type(exc).__name__}")

    @classmethod
    def get_migration_status(cls) -> dict[str, Any]:
        """
        Check PostgreSQL pgvector database connectivity, vector count metrics, and model versions.
        """
        pg_healthy = False
        candidate_count = 0
        vacancy_count = 0

        try:
            from app.core.database import pg_SessionLocal
            from app.models.pg import CandidateEmbedding, VacancyEmbedding

            if pg_SessionLocal is not None:
                with pg_SessionLocal() as session:
                    candidate_count = session.scalar(select(func.count(CandidateEmbedding.cv_key))) or 0
                    vacancy_count = session.scalar(select(func.count(VacancyEmbedding.vacancy_id))) or 0
                    pg_healthy = True
        except Exception as exc:
            logger.warning(f"[VECTOR_STATUS] PostgreSQL connection error: {exc}")

        return {
            "pgvector_enabled": settings.EMBEDDING_ENABLED,
            "pg_database_connected": pg_healthy,
            "embedding_model": settings.EMBEDDING_MODEL,
            "candidate_embeddings_count": candidate_count,
            "vacancy_embeddings_count": vacancy_count,
            "semantic_retrieval_top_n": settings.SEMANTIC_RETRIEVAL_TOP_N,
        }
