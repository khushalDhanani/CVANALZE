from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from redis import Redis
from rq import Queue, Retry, Worker, get_current_job
from rq.registry import ScheduledJobRegistry, StartedJobRegistry

from app.core.analysis_context import analysis_run_context
from app.core.config import settings
from app.core.cv_identity import normalize_source_candidate_id
from app.core.error_handlers import DocumentExtractionTimeoutError, PromptError
from app.core.logging import logger
from app.core.rule_config_manager import RuleConfigManager
from app.repositories.processing_job import ProcessingJobPersistenceError, ProcessingJobRepository
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


class ProcessingQueueFullError(ProcessingQueueUnavailableError):
    pass


@dataclass(frozen=True)
class QueueSubmission:
    record: ProcessingJobRecord
    reused_existing_job: bool = False


class ProcessingQueueService:
    """Persist, enqueue, and execute content-addressed CV processing jobs."""

    _RQ_ENQUEUE_VISIBILITY_GRACE_SECONDS = 30
    _SUBMISSION_LOCK_KEY = "lock:cv-processing:submission"

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
        source_candidate_id: str | int | None = None,
        cv_id: str | int | None = None,
        force_reprocess: bool = False,
    ) -> QueueSubmission:
        try:
            RuleConfigManager.get_config(tenant_id=None)
        except Exception as exc:
            raise ProcessingQueueUnavailableError("CV processing configuration is unavailable.") from exc

        job_id = ProcessingJobRepository.build_job_id(cv_key, content_hash)
        connection = cls._redis_connection()
        if connection is None:
            raise ProcessingQueueUnavailableError("Redis/RQ is unavailable; CV processing was not queued.")

        with cls._submission_lock(connection):
            existing = ProcessingJobRepository.get(job_id)
            if existing:
                existing = cls.reconcile_job(existing, connection=connection)
            if cls._can_reuse(existing, force_reprocess=force_reprocess):
                return QueueSubmission(record=existing, reused_existing_job=True)

            queue = Queue(settings.RQ_QUEUE_NAME, connection=connection)
            if cls._queue_load(queue, connection) >= settings.CV_QUEUE_MAX_SIZE:
                raise ProcessingQueueFullError("CV_QUEUE_FULL")

            enqueue_count = (existing.enqueue_count if existing else 0) + 1
            rq_job_id = f"{job_id}-{enqueue_count}"
            record = ProcessingJobRecord(
                job_id=job_id,
                cv_key=cv_key,
                content_hash=content_hash,
                filename=filename,
                storage_filename=storage_filename,
                content_type=content_type,
                candidate_id=str(candidate_id) if candidate_id is not None else None,
                source_candidate_id=normalize_source_candidate_id(source_candidate_id if source_candidate_id is not None else candidate_id),
                cv_id=str(cv_id) if cv_id is not None else None,
                parser_version=settings.EXTRACTION_PARSER_VERSION,
                schema_version=settings.EXTRACTION_SCHEMA_VERSION,
                state=JobState.QUEUED,
                progress=10,
                stage="queued",
                message="10% - CV processing is queued in RQ.",
                execution_mode=ProcessingExecutionMode.RQ,
                rq_job_id=rq_job_id,
                max_attempts=max(1, settings.RQ_MAX_RETRIES + 1),
                enqueue_count=enqueue_count,
                force_reprocess=force_reprocess,
                created_at=existing.created_at if existing else datetime.now(timezone.utc),
            )
            record = ProcessingJobRepository.save(record)

            try:
                cls._enqueue_record(record, connection)
                return QueueSubmission(record=record)
            except Exception as exc:
                logger.exception(f"RQ enqueue failed for '{job_id}': {type(exc).__name__}")
                error = CanonicalError(
                    code=ErrorCode.DEPENDENCY_UNAVAILABLE,
                    message="Redis/RQ rejected the CV processing job.",
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
                raise ProcessingQueueUnavailableError(error.message) from exc

    @staticmethod
    def legacy_status_payload(record: ProcessingJobRecord) -> dict[str, Any]:
        status = {
            JobState.COMPLETED: "COMPLETED",
            JobState.COMPLETED_DEGRADED: "COMPLETED_DEGRADED",
            JobState.FAILED: "FAILED",
            JobState.CANCELLED: "CANCELLED",
        }.get(record.state, "processing")
        return {
            "message": record.message,
            "cv_key": record.cv_key,
            "status": status,
            "progress": record.progress,
            "stage": record.stage,
            "failed_step": record.stage if record.state == JobState.FAILED else None,
            "error_details": None,
            "error_code": record.error.code.value if record.error else None,
            "error_message": record.error.message if record.error else None,
            "error_retryable": record.error.retryable if record.error else None,
            "correlation_id": record.error.correlation_id if record.error else None,
            "analysis_run_id": record.rq_job_id or record.job_id,
            "job_id": record.job_id,
            "job_state": record.state,
            "execution_mode": record.execution_mode.value,
            "retry_count": record.attempt,
            "persistence_status": "degraded" if record.state == JobState.COMPLETED_DEGRADED else None,
            "persistence_error": record.error.message if record.state == JobState.COMPLETED_DEGRADED and record.error else None,
        }

    @classmethod
    def list_jobs(cls) -> list[ProcessingJobRecord]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, settings.CV_JOB_HISTORY_HOURS))
        records = ProcessingJobRepository.list_recent(updated_since=cutoff, limit=settings.CV_JOB_LIST_LIMIT)
        connection = cls._redis_connection()
        reconciled = [cls.reconcile_job(record, connection=connection, allow_recovery=True) for record in records]
        return sorted(
            reconciled,
            key=lambda record: (
                0 if record.state in ProcessingJobRepository.ACTIVE_STATES else 1,
                record.enqueue_sequence or 0 if record.state in ProcessingJobRepository.ACTIVE_STATES else -record.updated_at.timestamp(),
                record.job_id,
            ),
        )

    @classmethod
    def reconcile_all_active_jobs(cls) -> dict[str, int]:
        records = ProcessingJobRepository.list_active()
        connection = cls._redis_connection()
        if connection is None:
            return {"examined": len(records), "updated": 0, "redis_unavailable": len(records)}
        updated = 0
        for record in records:
            reconciled = cls.reconcile_job(record, connection=connection, allow_recovery=True)
            if reconciled.version != record.version or reconciled.state != record.state:
                updated += 1
        return {"examined": len(records), "updated": updated, "redis_unavailable": 0}

    @classmethod
    def reconcile_job(
        cls,
        record: ProcessingJobRecord,
        *,
        connection: Redis | None = None,
        allow_recovery: bool = False,
    ) -> ProcessingJobRecord:
        """Sync application state with RQ if the job crashed abruptly."""
        if record.execution_mode != ProcessingExecutionMode.RQ or record.state not in (JobState.QUEUED, JobState.PROCESSING, JobState.RETRYING):
            return record

        if not record.rq_job_id:
            return record

        connection = connection or cls._redis_connection()
        if not connection:
            return record

        try:
            from rq.job import Job, NoSuchJobError
            try:
                rq_job = Job.fetch(record.rq_job_id, connection=connection)
                raw_rq_status = rq_job.get_status(refresh=True)
                rq_status = str(getattr(raw_rq_status, "value", raw_rq_status)).lower()
                if rq_status == "started":
                    if allow_recovery and cls._is_started_job_stale(record, rq_job, connection):
                        return cls._recover_or_fail(record, connection, ErrorCode.WORKER_LOST)
                    if record.state != JobState.PROCESSING:
                        return ProcessingJobRepository.transition(
                            record.job_id,
                            JobState.PROCESSING,
                            progress=max(15, record.progress),
                            stage="worker_started",
                            message="CV processing worker started the job.",
                        )
                    return record
                if rq_status == "scheduled" and record.state != JobState.RETRYING:
                    return ProcessingJobRepository.transition(
                        record.job_id,
                        JobState.RETRYING,
                        stage="retry_wait",
                        message="CV processing is waiting for its next RQ retry.",
                    )
                if rq_status == "queued" and record.state == JobState.PROCESSING:
                    return ProcessingJobRepository.transition(
                        record.job_id,
                        JobState.RETRYING,
                        stage="recovered_queue",
                        message="CV processing was recovered and is waiting in the RQ queue.",
                    )
                if rq_status in ("canceled", "cancelled", "stopped"):
                    return ProcessingJobRepository.transition(
                        record.job_id,
                        JobState.CANCELLED,
                        progress=100,
                        stage="cancelled",
                        message="CV processing was cancelled.",
                    )
                if rq_status == "failed":
                    error = CanonicalError(
                        code=ErrorCode.PROCESSING_FAILED,
                        message="CV processing failed abruptly during background execution.",
                        retryable=False,
                        correlation_id=record.rq_job_id,
                    )
                    return ProcessingJobRepository.transition(
                        record.job_id,
                        JobState.FAILED,
                        progress=100,
                        stage="failed",
                        message=error.message,
                        error=error,
                    )
                if rq_status == "finished":
                    result = ResultRepository.resolve_result(record.cv_key)
                    result_status = str(result.get("status") or "").upper() if result else ""
                    result_complete = bool(result) and (
                        result_status in ("COMPLETED", "COMPLETED_DEGRADED", "NEW_CV", "REPROCESSED", "CACHE_HIT")
                        or result.get("progress") == 100
                        or result.get("is_complete") is True
                    )
                    if result_complete and result is not None:
                        degraded = result.get("persistence_status") == ResultRepository.PERSISTENCE_DEGRADED
                        persistence_error = None
                        if degraded:
                            persistence_error = CanonicalError(
                                code=ErrorCode.DEPENDENCY_UNAVAILABLE,
                                message=ResultRepository.PERSISTENCE_ERROR_MESSAGE,
                                retryable=True,
                                correlation_id=record.rq_job_id,
                            )
                        completion_record = record
                        if completion_record.state != JobState.PROCESSING:
                            completion_record = ProcessingJobRepository.transition(
                                completion_record.job_id,
                                JobState.PROCESSING,
                                progress=max(15, completion_record.progress),
                                stage="result_reconciliation",
                                message="Reconciling the completed RQ result.",
                            )
                        return ProcessingJobRepository.transition(
                            completion_record.job_id,
                            JobState.COMPLETED_DEGRADED if degraded else JobState.COMPLETED,
                            progress=100,
                            stage="complete_degraded" if degraded else "complete",
                            message=(
                                ResultRepository.PERSISTENCE_ERROR_MESSAGE
                                if degraded
                                else "CV processing completed successfully."
                            ),
                            error=persistence_error,
                        )
                    error = CanonicalError(
                        code=ErrorCode.PROCESSING_FAILED,
                        message="CV processing ended without producing a durable result.",
                        retryable=False,
                        correlation_id=record.rq_job_id,
                    )
                    return ProcessingJobRepository.transition(
                        record.job_id,
                        JobState.FAILED,
                        progress=100,
                        stage="missing_result",
                        message=error.message,
                        error=error,
                    )
            except NoSuchJobError:
                queued_age = (datetime.now(timezone.utc) - record.updated_at).total_seconds()
                if record.state == JobState.QUEUED and queued_age < cls._RQ_ENQUEUE_VISIBILITY_GRACE_SECONDS:
                    return record
                if allow_recovery:
                    return cls._recover_or_fail(record, connection, ErrorCode.JOB_STUCK)
                error = CanonicalError(
                    code=ErrorCode.PROCESSING_FAILED,
                    message="The background processing job is no longer available.",
                    retryable=True,
                    correlation_id=record.rq_job_id,
                )
                return ProcessingJobRepository.transition(
                    record.job_id,
                    JobState.FAILED,
                    progress=100,
                    stage="missing_queue_job",
                    message="CV processing stopped because its background queue job disappeared. Upload the CV again to retry.",
                    error=error,
                )
        except ProcessingJobPersistenceError:
            raise
        except Exception as e:
            logger.warning(f"Failed to reconcile RQ job {record.rq_job_id}: {e}")

        return record

    @classmethod
    def _is_started_job_stale(cls, record: ProcessingJobRecord, rq_job: Any, connection: Redis) -> bool:
        threshold = max(settings.CV_JOB_STALE_AFTER_SECONDS, settings.RQ_MAINTENANCE_INTERVAL_SECONDS * 2)
        now = datetime.now(timezone.utc)
        heartbeats = [record.heartbeat_at, record.updated_at, getattr(rq_job, "last_heartbeat", None)]
        worker_name = str(getattr(rq_job, "worker_name", "") or "")
        try:
            workers = Worker.all(connection=connection)
            matching_worker = next((worker for worker in workers if worker.name == worker_name), None)
            if matching_worker is not None:
                current_job_id = matching_worker.get_current_job_id()
                if current_job_id == record.rq_job_id:
                    heartbeats.append(getattr(matching_worker, "last_heartbeat", None))
                    latest = cls._latest_utc(heartbeats)
                    return latest is not None and (now - latest).total_seconds() > threshold
            elif worker_name:
                latest = cls._latest_utc(heartbeats)
                return latest is None or (now - latest).total_seconds() > threshold
        except Exception as exc:
            logger.warning("Could not inspect RQ worker heartbeat for %s: %s", record.rq_job_id, type(exc).__name__)
            return False
        latest = cls._latest_utc(heartbeats)
        return latest is not None and (now - latest).total_seconds() > threshold

    @staticmethod
    def _latest_utc(values: list[datetime | None]) -> datetime | None:
        normalized = []
        for value in values:
            if value is None:
                continue
            normalized.append(value if value.tzinfo else value.replace(tzinfo=timezone.utc))
        return max(normalized) if normalized else None

    @classmethod
    def _recover_or_fail(cls, record: ProcessingJobRecord, connection: Redis, reason: ErrorCode) -> ProcessingJobRecord:
        lock = connection.lock(f"lock:cv-processing:recovery:{record.job_id}", timeout=30, blocking_timeout=0)
        if not lock.acquire(blocking=False):
            return ProcessingJobRepository.get(record.job_id) or record
        try:
            current = ProcessingJobRepository.get(record.job_id) or record
            if current.rq_job_id != record.rq_job_id or current.state not in ProcessingJobRepository.ACTIVE_STATES:
                return current
            if current.attempt >= current.max_attempts:
                error = CanonicalError(
                    code=reason,
                    message="CV processing stopped after its worker became unavailable.",
                    retryable=False,
                    correlation_id=current.rq_job_id,
                )
                return ProcessingJobRepository.transition(
                    current.job_id,
                    JobState.FAILED,
                    progress=100,
                    stage="worker_lost" if reason == ErrorCode.WORKER_LOST else "stuck_job",
                    message=error.message,
                    error=error,
                )

            enqueue_count = current.enqueue_count + 1
            rq_job_id = f"{current.job_id}-{enqueue_count}"
            retry_error = CanonicalError(
                code=reason,
                message="CV processing is being recovered after its previous queue execution stopped.",
                retryable=True,
                correlation_id=current.rq_job_id,
            )
            recovered_state = JobState.QUEUED if current.state == JobState.QUEUED else JobState.RETRYING
            recovered = ProcessingJobRepository.transition(
                current.job_id,
                recovered_state,
                rq_job_id=rq_job_id,
                enqueue_count=enqueue_count,
                stage="recovered_queue",
                message=retry_error.message,
                error=retry_error,
                heartbeat_at=None,
            )
            cls._enqueue_record(recovered, connection)
            return recovered
        except Exception as exc:
            logger.exception("Could not recover CV processing job %s: %s", record.job_id, type(exc).__name__)
            return ProcessingJobRepository.get(record.job_id) or record
        finally:
            try:
                lock.release()
            except Exception:
                pass

    @classmethod
    def _enqueue_record(cls, record: ProcessingJobRecord, connection: Redis) -> None:
        options: dict[str, Any] = {
            "job_id": record.rq_job_id,
            "job_timeout": settings.RQ_JOB_TIMEOUT_SECONDS,
            "result_ttl": settings.RQ_RESULT_TTL_SECONDS,
            "failure_ttl": settings.RQ_RESULT_TTL_SECONDS,
            "unique": True,
        }
        if settings.RQ_MAX_RETRIES > 0:
            options["retry"] = Retry(max=settings.RQ_MAX_RETRIES, interval=max(0, settings.RQ_RETRY_INTERVAL_SECONDS))
        Queue(settings.RQ_QUEUE_NAME, connection=connection).enqueue(
            process_cv_job,
            record.job_id,
            record.enqueue_count,
            **options,
        )

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
        if existing.state in (JobState.COMPLETED, JobState.COMPLETED_DEGRADED):
            return ResultRepository.resolve_result(existing.cv_key) is not None
        return False

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
    @contextmanager
    def _submission_lock(cls, connection: Redis) -> Iterator[None]:
        lock = connection.lock(
            cls._SUBMISSION_LOCK_KEY,
            timeout=settings.PROCESSING_JOB_LOCK_TIMEOUT_SECONDS,
            blocking_timeout=10,
        )
        try:
            acquired = lock.acquire(blocking=True)
        except Exception as exc:
            raise ProcessingQueueUnavailableError("Redis/RQ is unavailable; CV processing was not queued.") from exc
        if not acquired:
            raise ProcessingQueueUnavailableError("CV queue submission is temporarily busy.")
        try:
            yield
        finally:
            try:
                lock.release()
            except Exception as exc:
                logger.warning(f"Could not release the CV queue submission lock: {exc}")

    @staticmethod
    def _queue_load(queue: Queue, connection: Redis) -> int:
        try:
            started = StartedJobRegistry(queue.name, connection=connection).count
            scheduled = ScheduledJobRegistry(queue.name, connection=connection).count
            redis_load = len(queue) + started + scheduled
            return max(redis_load, ProcessingJobRepository.count_active())
        except Exception as exc:
            raise ProcessingQueueUnavailableError("Redis/RQ queue capacity is unavailable.") from exc


def process_cv_job(job_id: str, expected_enqueue_count: int | None = None) -> dict[str, Any]:
    """RQ entry point. Load the retained source, revalidate it, and run the async pipeline."""
    record = ProcessingJobRepository.get(job_id)
    if record is None:
        raise LookupError(f"Processing job '{job_id}' was not found.")
    rq_job = get_current_job()
    if expected_enqueue_count is not None and record.enqueue_count != expected_enqueue_count:
        return {"job_id": job_id, "status": "STALE_ATTEMPT"}
    if rq_job is not None and record.rq_job_id and rq_job.id != record.rq_job_id:
        return {"job_id": job_id, "status": "STALE_ATTEMPT"}
    if record.state == JobState.COMPLETED and ResultRepository.resolve_result(record.cv_key):
        return {"job_id": job_id, "status": JobState.COMPLETED}
    if record.state == JobState.CANCELLED:
        return {"job_id": job_id, "status": JobState.CANCELLED}

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
        persistence_degraded = (
            result.get("persistence_status") == ResultRepository.PERSISTENCE_DEGRADED
            or str(result.get("status") or "").upper() == JobState.COMPLETED_DEGRADED
        )
        completed_state = JobState.COMPLETED_DEGRADED if persistence_degraded else JobState.COMPLETED
        persistence_error = None
        if persistence_degraded:
            persistence_error = CanonicalError(
                code=ErrorCode.DEPENDENCY_UNAVAILABLE,
                message=ResultRepository.PERSISTENCE_ERROR_MESSAGE,
                retryable=True,
            )
        ProcessingJobRepository.transition(
            job_id,
            completed_state,
            progress=100,
            stage="complete_degraded" if persistence_degraded else "complete",
            message=(
                "CV processing completed, but PostgreSQL result persistence failed."
                if persistence_degraded
                else result.get("message") or "100% - CV processing complete."
            ),
            outcome=outcome,
            error=persistence_error,
        )
        return result
    except Exception as exc:
        logger.exception(f"Processing job '{job_id}' failed on attempt {attempt}: {type(exc).__name__}")
        current = ProcessingJobRepository.get(job_id) or record
        from app.services.ollama_transport import OllamaError, OllamaInvalidResponseError

        terminal_error = (
            isinstance(exc, (DocumentExtractionTimeoutError, PromptError, OllamaInvalidResponseError))
            or isinstance(exc, OllamaError) and not exc.retryable
        )
        will_retry = not terminal_error and attempt < current.max_attempts
        state = JobState.RETRYING if will_retry else JobState.FAILED
        error = _safe_processing_error(exc, retryable=will_retry, correlation_id=current.rq_job_id)
        ProcessingJobRepository.transition(
            job_id,
            state,
            progress=current.progress if will_retry else 100,
            stage="retry_wait" if will_retry else "failed",
            message=(f"{error.message} Waiting to retry." if will_retry else error.message),
            error=error,
        )
        if not will_retry:
            UploadService.cleanup_after_processing(record.storage_filename, succeeded=False)
        if isinstance(exc, PromptError):
            return {"job_id": job_id, "status": JobState.FAILED, "error_code": ErrorCode.PROMPT_UNAVAILABLE.value}
        if isinstance(exc, DocumentExtractionTimeoutError):
            return {"job_id": job_id, "status": JobState.FAILED, "error_code": ErrorCode.JOB_STUCK.value}
        raise


def _safe_processing_error(exc: Exception, *, retryable: bool, correlation_id: str | None) -> CanonicalError:
    from app.services.ollama_transport import (
        OllamaHTTPError,
        OllamaInvalidResponseError,
        OllamaModelUnavailableError,
        OllamaTimeoutError,
        OllamaUnavailableError,
    )

    error_name = type(exc).__name__.lower()
    if isinstance(exc, OllamaTimeoutError):
        code = ErrorCode.LLM_TIMEOUT
        message = "LLM generation exceeded the allowed time."
    elif isinstance(exc, (OllamaUnavailableError, OllamaModelUnavailableError, OllamaHTTPError)):
        code = ErrorCode.LLM_UNAVAILABLE
        message = "The configured LLM service is unavailable."
    elif isinstance(exc, OllamaInvalidResponseError):
        code = ErrorCode.ANALYSIS_INVALID
        message = "The LLM response failed structured analysis validation."
        retryable = False
    elif isinstance(exc, FileNotFoundError):
        code = ErrorCode.NOT_FOUND
        message = "The retained CV source was unavailable during processing."
    elif isinstance(exc, PromptError):
        code = ErrorCode.PROMPT_UNAVAILABLE
        message = "CV processing is unavailable because the required optimized matching prompt is not ready."
        retryable = False
    elif "timeout" in error_name:
        code = ErrorCode.JOB_STUCK
        message = "CV processing exceeded the allowed execution time."
    elif "connection" in error_name or "operational" in error_name or "database" in error_name:
        code = ErrorCode.DEPENDENCY_UNAVAILABLE
        message = "A required processing service became temporarily unavailable."
    elif isinstance(exc, ValueError):
        code = ErrorCode.VALIDATION_ERROR
        message = "The retained CV could not be validated for processing."
    else:
        code = ErrorCode.PROCESSING_FAILED
        message = "CV processing failed during background execution."
    return CanonicalError(code=code, message=message, retryable=retryable, correlation_id=correlation_id)


async def _process_source(
    *,
    record: ProcessingJobRecord,
    filename: str,
    content: bytes,
    content_type: str | None,
    storage_filename: str,
) -> dict[str, Any]:
    from app.services.cv_service import process_cv_file

    analysis_run_id = record.rq_job_id or record.job_id
    with analysis_run_context(analysis_run_id, record.cv_key):
        return await process_cv_file(
            filename=filename,
            content=content,
            content_type=content_type,
            candidate_id=record.candidate_id,
            source_candidate_id=record.source_candidate_id,
            cv_id=record.cv_id,
            force_reprocess=record.force_reprocess,
            storage_filename=storage_filename,
            analysis_run_id=analysis_run_id,
            job_id=record.job_id,
        )


def handle_work_horse_killed(job, _retpid, _ret_val, _rusage) -> None:
    """Persist an RQ workhorse crash without preventing the worker from taking the next CV."""
    if not job.args:
        return
    job_id = str(job.args[0])
    record = ProcessingJobRepository.get(job_id)
    if record is None or record.state not in (JobState.PROCESSING, JobState.RETRYING):
        return
    will_retry = bool(getattr(job, "retries_left", 0))
    error = CanonicalError(
        code=ErrorCode.PROCESSING_FAILED,
        message="The CV processing workhorse terminated unexpectedly.",
        retryable=will_retry,
        correlation_id=str(getattr(job, "id", "") or "") or None,
    )
    ProcessingJobRepository.transition(
        job_id,
        JobState.RETRYING if will_retry else JobState.FAILED,
        progress=record.progress if will_retry else 100,
        stage="retry_wait" if will_retry else "worker_crash",
        message="CV processing will retry after a worker crash." if will_retry else "CV processing failed after a worker crash.",
        error=error,
    )
