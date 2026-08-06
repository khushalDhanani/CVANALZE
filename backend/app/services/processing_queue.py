from __future__ import annotations
import asyncio
import hashlib
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timezone, datetime
from typing import Any

from redis import Redis
from rq import Queue, Retry

from app.core.config import settings
from app.core.logging import logger
from app.repositories.processing_job import ProcessingJobRepository
from app.repositories.result import ResultRepository
from app.schemas.contracts import (
    CanonicalError,
    ErrorCode,
    JobState,
    ProcessingExecutionMode,
    ProcessingJobRecord,
    ProcessingOutcome,
)
from app.services.upload_service import UploadService


class ProcessingQueueUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class QueueSubmission:
    record: ProcessingJobRecord
    schedule_development_fallback: bool = False
    reused_existing_job: bool = False


class ProcessingQueueService:
    """Persist, enqueue, and execute content-addressed CV processing jobs."""

    _local_locks: dict[str, threading.Lock] = {}
    _local_locks_guard = threading.Lock()
    _MAX_LOCAL_LOCKS = 1000

    @classmethod
    def submit_upload(
        cls,
        *,
        cv_key: str,
        content_hash: str,
        filename: str,
        storage_filename: str,
        content_type: str | None,
        candidate_id: str | int | None = None,
        cv_id: str | int | None = None,
        force_reprocess: bool = False,
    ) -> QueueSubmission:
        job_id = ProcessingJobRepository.build_job_id(cv_key, content_hash)
        connection = cls._redis_connection()

        with cls._job_lock(f"submit:{job_id}", connection):
            existing = ProcessingJobRepository.get(job_id)
            if cls._can_reuse(existing, force_reprocess=force_reprocess):
                return QueueSubmission(record=existing, reused_existing_job=True)

            enqueue_count = (existing.enqueue_count if existing else 0) + 1
            record = ProcessingJobRecord(
                job_id=job_id,
                cv_key=cv_key,
                content_hash=content_hash,
                filename=filename,
                storage_filename=storage_filename,
                content_type=content_type,
                candidate_id=str(candidate_id) if candidate_id is not None else None,
                cv_id=str(cv_id) if cv_id is not None else None,
                parser_version=settings.EXTRACTION_PARSER_VERSION,
                schema_version=settings.EXTRACTION_SCHEMA_VERSION,
                state=JobState.QUEUED,
                progress=10,
                stage="queued",
                message="10% - CV processing is queued.",
                execution_mode=ProcessingExecutionMode.PENDING,
                max_attempts=max(1, settings.RQ_MAX_RETRIES + 1),
                enqueue_count=enqueue_count,
                force_reprocess=force_reprocess,
                created_at=existing.created_at if existing else datetime.now(timezone.utc),
            )
            record = ProcessingJobRepository.save(record)

            if connection is not None:
                try:
                    rq_job_id = f"{job_id}-{enqueue_count}"
                    record = ProcessingJobRepository.save(
                        record.model_copy(
                            update={
                                "execution_mode": ProcessingExecutionMode.RQ,
                                "rq_job_id": rq_job_id,
                                "message": "10% - CV processing is queued in RQ.",
                            }
                        )
                    )
                    enqueue_options: dict[str, Any] = {
                        "job_id": rq_job_id,
                        "job_timeout": settings.RQ_JOB_TIMEOUT_SECONDS,
                        "result_ttl": settings.RQ_RESULT_TTL_SECONDS,
                    }
                    if settings.RQ_MAX_RETRIES > 0:
                        enqueue_options["retry"] = Retry(
                            max=settings.RQ_MAX_RETRIES,
                            interval=max(0, settings.RQ_RETRY_INTERVAL_SECONDS),
                        )
                    Queue(settings.RQ_QUEUE_NAME, connection=connection).enqueue(
                        process_cv_job,
                        job_id,
                        **enqueue_options,
                    )
                    return QueueSubmission(record=record)
                except Exception as exc:
                    logger.warning(f"RQ enqueue failed for '{job_id}': {exc}")

            if cls._development_fallback_allowed():
                record = ProcessingJobRepository.save(
                    record.model_copy(
                        update={
                            "execution_mode": ProcessingExecutionMode.DEVELOPMENT_FALLBACK,
                            "message": "10% - Redis unavailable; queued in explicit development fallback.",
                        }
                    )
                )
                logger.warning(f"Using development background fallback for processing job '{job_id}'.")
                return QueueSubmission(record=record, schedule_development_fallback=True)

            error = CanonicalError(
                code=ErrorCode.DEPENDENCY_UNAVAILABLE,
                message="Redis/RQ is unavailable and the development fallback is disabled.",
                retryable=True,
            )
            ProcessingJobRepository.transition(
                job_id,
                JobState.FAILED,
                progress=100,
                stage="enqueue",
                message=error.message,
                error=error,
            )
            raise ProcessingQueueUnavailableError(error.message)

    @staticmethod
    def legacy_status_payload(record: ProcessingJobRecord) -> dict[str, Any]:
        status = {
            JobState.COMPLETED: "COMPLETED",
            JobState.FAILED: "FAILED",
        }.get(record.state, "processing")
        return {
            "message": record.message,
            "cv_key": record.cv_key,
            "status": status,
            "progress": record.progress,
            "stage": record.stage,
            "failed_step": record.stage if record.state == JobState.FAILED else None,
            "error_details": None,
            "job_id": record.job_id,
            "job_state": record.state,
            "execution_mode": record.execution_mode.value,
            "retry_count": record.attempt,
        }

    @staticmethod
    def unknown_job_compatibility_active() -> bool:
        deadline = settings.JOB_NOT_FOUND_COMPATIBILITY_UNTIL
        if deadline is None:
            return False
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < deadline

    @classmethod
    def _can_reuse(
        cls,
        existing: ProcessingJobRecord | None,
        *,
        force_reprocess: bool,
    ) -> bool:
        if existing is None:
            return False
        if existing.state in (JobState.QUEUED, JobState.PROCESSING, JobState.RETRYING):
            return existing.execution_mode != ProcessingExecutionMode.PENDING
        if force_reprocess:
            return False
        if existing.state == JobState.COMPLETED:
            return ResultRepository.resolve_result(existing.cv_key) is not None
        return False

    @staticmethod
    def _development_fallback_allowed() -> bool:
        environment = settings.APP_ENVIRONMENT.strip().lower()
        return settings.RQ_DEVELOPMENT_FALLBACK_ENABLED and environment in {
            "dev",
            "development",
            "local",
            "test",
        }

    @staticmethod
    def _redis_connection() -> Redis | None:
        if not settings.REDIS_URL:
            return None
        try:
            connection = Redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
            connection.ping()
            return connection
        except Exception as exc:
            logger.warning(f"Redis/RQ is unavailable: {exc}")
            return None

    @classmethod
    def _get_local_lock(cls, key: str) -> threading.Lock:
        with cls._local_locks_guard:
            if key not in cls._local_locks:
                if len(cls._local_locks) >= cls._MAX_LOCAL_LOCKS:
                    cls._local_locks.pop(next(iter(cls._local_locks)), None)
                cls._local_locks[key] = threading.Lock()
            return cls._local_locks[key]

    @classmethod
    @contextmanager
    def _job_lock(cls, key: str, connection: Redis | None = None) -> Iterator[None]:
        redis_lock = None
        if connection is not None:
            redis_lock = connection.lock(
                f"lock:processing-job:{key}",
                timeout=settings.PROCESSING_JOB_LOCK_TIMEOUT_SECONDS,
                blocking_timeout=10,
            )
            if not redis_lock.acquire(blocking=True):
                raise ProcessingQueueUnavailableError(f"Processing lock for '{key}' is busy.")

        local_lock = cls._get_local_lock(key)
        with local_lock:
            try:
                yield
            finally:
                if redis_lock is not None:
                    try:
                        redis_lock.release()
                    except Exception as exc:
                        logger.warning(f"Could not release processing lock '{key}': {exc}")


def process_cv_job(job_id: str) -> dict[str, Any]:
    """RQ entry point. Load the retained source, revalidate it, and run the async pipeline."""
    record = ProcessingJobRepository.get(job_id)
    if record is None:
        raise LookupError(f"Processing job '{job_id}' was not found.")
    connection = ProcessingQueueService._redis_connection()

    with ProcessingQueueService._job_lock(f"execute:{job_id}", connection):
        record = ProcessingJobRepository.get(job_id)
        if record is None:
            raise LookupError(f"Processing job '{job_id}' was not found.")
        if record.state == JobState.COMPLETED and ResultRepository.resolve_result(record.cv_key):
            return {"job_id": job_id, "status": JobState.COMPLETED}

        attempt = record.attempt + 1
        ProcessingJobRepository.transition(
            job_id,
            JobState.PROCESSING,
            attempt=attempt,
            progress=max(15, record.progress),
            stage="source_validation",
            message=f"Processing attempt {attempt} of {record.max_attempts}.",
            error=None,
            completed_at=None,
        )

        try:
            source = UploadService.load_reprocessable_upload(
                storage_filename=record.storage_filename,
                original_filename=record.filename,
                cv_key=record.cv_key,
            )
            if source is None:
                raise FileNotFoundError("The retained source CV is unavailable for processing.")
            source_hash = hashlib.sha256(source.content).hexdigest()
            if source_hash != record.content_hash:
                raise ValueError("The retained source CV no longer matches the queued content identity.")

            result = asyncio.run(
                _process_source(
                    record=record,
                    filename=source.safe_filename,
                    content=source.content,
                    content_type=source.detected_content_type,
                    storage_filename=source.storage_filename,
                )
            )
            raw_outcome = str(result.get("original_status") or result.get("status") or "").upper()
            try:
                outcome = ProcessingOutcome(raw_outcome)
            except ValueError:
                outcome = None
            ProcessingJobRepository.transition(
                job_id,
                JobState.COMPLETED,
                progress=100,
                stage="complete",
                message=result.get("message") or "100% - CV processing complete.",
                outcome=outcome,
                error=None,
            )
            return result
        except Exception as exc:
            logger.exception(f"Processing job '{job_id}' failed on attempt {attempt}: {type(exc).__name__}")
            current = ProcessingJobRepository.get(job_id) or record
            will_retry = attempt < current.max_attempts
            state = JobState.RETRYING if will_retry else JobState.FAILED
            error = CanonicalError(
                code=ErrorCode.PROCESSING_FAILED,
                message="CV processing failed during background execution.",
                retryable=will_retry,
            )
            ProcessingJobRepository.transition(
                job_id,
                state,
                progress=current.progress if will_retry else 100,
                stage="retry_wait" if will_retry else "failed",
                message=(f"Processing attempt {attempt} failed; waiting to retry." if will_retry else f"CV processing failed after {attempt} attempt(s)."),
                error=error,
            )
            if not will_retry:
                UploadService.cleanup_after_processing(record.storage_filename, succeeded=False)
            raise


async def _process_source(
    *,
    record: ProcessingJobRecord,
    filename: str,
    content: bytes,
    content_type: str | None,
    storage_filename: str,
) -> dict[str, Any]:
    from app.services.cv_service import process_cv_file

    return await process_cv_file(
        filename=filename,
        content=content,
        content_type=content_type,
        candidate_id=record.candidate_id,
        cv_id=record.cv_id,
        force_reprocess=record.force_reprocess,
        storage_filename=storage_filename,
    )


def run_processing_job_fallback(job_id: str) -> None:
    """Development-only in-process runner with the same persisted retry states as RQ."""
    while True:
        try:
            process_cv_job(job_id)
            return
        except Exception:
            record = ProcessingJobRepository.get(job_id)
            if record is None or record.state != JobState.RETRYING:
                return
            time.sleep(max(0, settings.RQ_RETRY_INTERVAL_SECONDS))
