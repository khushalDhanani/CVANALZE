from __future__ import annotations

import logging
from typing import Any, Callable

from redis import Redis
from redis.exceptions import LockError
from rq import get_current_job

from app.core.config import settings

logger = logging.getLogger(__name__)

_SYNC_LOCK_KEY = "cv-analyzer:background-sync"
_CV_JOB_RECONCILIATION_LOCK_KEY = "cv-analyzer:cv-job-reconciliation"


def _redis_connection() -> Redis:
    current_job = get_current_job()
    if current_job is not None:
        return current_job.connection
    return Redis.from_url(
        settings.REDIS_URL,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
        socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
        socket_keepalive=True,
        retry_on_timeout=True,
        health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS,
    )


def _run_with_lock(lock_key: str, task: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    lock = _redis_connection().lock(lock_key, timeout=settings.BACKGROUND_SYNC_LOCK_TIMEOUT_SECONDS)
    if not lock.acquire(blocking=False):
        logger.info("Skipping recurring task because another execution owns lock %s.", lock_key)
        return {"status": "skipped", "reason": "already_running"}

    try:
        return task()
    finally:
        try:
            lock.release()
        except LockError:
            logger.warning("Recurring task lock %s expired before release.", lock_key)


def run_integration_sync() -> dict[str, Any]:
    """Synchronize every canonical MSSQL snapshot into PostgreSQL."""
    from app.services.integration_sync_service import CandidateSyncService, ReferenceSyncService, VacancySyncService

    def execute() -> dict[str, Any]:
        results = ReferenceSyncService.sync_all()
        results["candidates"] = CandidateSyncService.run_sync()
        results["vacancies"] = VacancySyncService.run_sync()

        failed_entities = [name for name, metrics in results.items() if metrics.get("status") in {"failed", "skipped"}]
        partial_entities = [name for name, metrics in results.items() if metrics.get("status") == "partial_failed"]
        if failed_entities:
            raise RuntimeError(f"Integration sync failed or was unavailable for: {', '.join(failed_entities)}")

        status = "completed_degraded" if partial_entities else "completed"
        logger.info("Canonical MSSQL snapshot sync finished with status=%s.", status)
        return {"status": status, "entities": results, "partial_entities": partial_entities}

    return _run_with_lock(_SYNC_LOCK_KEY, execute)


def snapshot_validation_metrics() -> dict[str, str]:
    """Persist a point-in-time validation metrics aggregate."""
    from app.services.shadow_validation_service import MetricsEngine

    MetricsEngine.snapshot_metrics()
    logger.info("Validation metrics snapshot task completed.")
    return {"status": "completed"}


def reconcile_cv_processing_jobs() -> dict[str, Any]:
    """Repair durable CV job state from RQ without executing CV work in the auxiliary lane."""
    from app.services.processing_queue import ProcessingQueueService

    return _run_with_lock(_CV_JOB_RECONCILIATION_LOCK_KEY, ProcessingQueueService.reconcile_all_active_jobs)
