from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, cast

from rq import Queue, Retry
from sqlalchemy import select

from app.core.config import settings
from app.core.cv_identity import resolve_cv_identity
from app.core.database import MssqlReadSession
from app.core.logging import logger
from app.models.mssql.candidate import RecruitCandidateMst
from app.repositories.batch_job import BatchJobRepository
from app.repositories.processing_job import ProcessingJobRepository
from app.repositories.result import ResultRepository
from app.schemas.batch import BatchJobItem, BatchJobRecord
from app.schemas.contracts import JobState
from app.services.processing_queue import ProcessingQueueService, ProcessingQueueUnavailableError
from app.services.upload_service import UploadService


class BatchProcessingService:
    @classmethod
    def submit(cls, limit: int) -> BatchJobRecord:
        batch_job_id = f"batch_{uuid.uuid4().hex}"
        record = BatchJobRepository.save(BatchJobRecord(batch_job_id=batch_job_id, limit=limit))
        connection = ProcessingQueueService._redis_connection()
        if connection is None:
            BatchJobRepository.update(batch_job_id, state="FAILED", stage="enqueue", progress=100, error="Redis/RQ is unavailable.")
            raise ProcessingQueueUnavailableError("Redis/RQ is unavailable; batch processing was not queued.")

        try:
            enqueue_options: dict[str, object] = {
                "job_id": batch_job_id,
                "job_timeout": settings.RQ_JOB_TIMEOUT_SECONDS,
                "result_ttl": settings.RQ_RESULT_TTL_SECONDS,
            }
            if settings.RQ_MAX_RETRIES > 0:
                enqueue_options["retry"] = Retry(
                    max=settings.RQ_MAX_RETRIES,
                    interval=max(0, settings.RQ_RETRY_INTERVAL_SECONDS),
                )
            Queue(settings.RQ_AUXILIARY_QUEUE_NAME, connection=connection).enqueue(process_batch_job, batch_job_id, **enqueue_options)
            return record
        except Exception as exc:
            logger.exception(f"Failed to enqueue batch job '{batch_job_id}': {type(exc).__name__}")
            BatchJobRepository.update(batch_job_id, state="FAILED", stage="enqueue", progress=100, error="Batch job enqueue failed.")
            raise ProcessingQueueUnavailableError("Batch job enqueue failed.") from exc

    @classmethod
    def get_status(cls, batch_job_id: str) -> BatchJobRecord | None:
        record = BatchJobRepository.get(batch_job_id)
        if record is None or record.state in ("COMPLETED", "COMPLETED_DEGRADED", "FAILED"):
            return record
        if record.stage != "cv_jobs_queued":
            return cls._reconcile_coordinator(record)

        processed = 0
        matches: list[dict[str, Any]] = []
        degraded = False
        for item in record.items:
            if item.error:
                processed += 1
                degraded = True
                matches.append(cls._error_result(item, item.error))
                continue
            child = ProcessingJobRepository.get(item.processing_job_id or "")
            if child is not None:
                child = ProcessingQueueService.reconcile_job(child)
            if child is None or child.state not in (JobState.COMPLETED, JobState.COMPLETED_DEGRADED, JobState.FAILED):
                continue
            processed += 1
            if child.state == JobState.FAILED:
                degraded = True
                matches.append(cls._error_result(item, child.message or "CV processing failed."))
                continue
            degraded = degraded or child.state == JobState.COMPLETED_DEGRADED
            result = ResultRepository.resolve_result(item.cv_key or "")
            if not result:
                degraded = True
                matches.append(cls._error_result(item, "Completed CV result is unavailable."))
                continue
            matches.append(
                {
                    "candidate_id": item.candidate_id,
                    "candidate_name": item.candidate_name,
                    "analysis": result.get("match_analysis") or {},
                    "status": child.state,
                }
            )

        total = record.total
        progress = 100 if total == 0 else min(100, 20 + int(processed * 80 / total))
        if processed < total:
            return BatchJobRepository.update(
                batch_job_id,
                processed=processed,
                progress=progress,
                matches=matches,
                message=f"Processed {processed} of {total} candidates.",
            )

        state = "COMPLETED_DEGRADED" if degraded else "COMPLETED"
        return BatchJobRepository.update(
            batch_job_id,
            state=state,
            stage="complete_degraded" if state == "COMPLETED_DEGRADED" else "complete",
            processed=processed,
            progress=100,
            matches=matches,
            message=f"Processed {processed} candidates through the standard CV pipeline.",
            completed_at=datetime.now(timezone.utc),
        )

    @classmethod
    def _reconcile_coordinator(cls, record: BatchJobRecord) -> BatchJobRecord:
        connection = ProcessingQueueService._redis_connection()
        if connection is None:
            return record
        try:
            from rq.job import Job, NoSuchJobError

            try:
                rq_job = Job.fetch(record.batch_job_id, connection=connection)
            except NoSuchJobError:
                return record
            if rq_job.get_status() != "failed":
                return record
            return BatchJobRepository.update(
                record.batch_job_id,
                state="FAILED",
                stage="failed",
                progress=100,
                error="Batch coordinator failed during background execution.",
                message="Batch processing failed before all CV jobs were queued.",
                completed_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            logger.warning(f"Failed to reconcile batch RQ job '{record.batch_job_id}': {exc}")
            return record

    @staticmethod
    def _error_result(item: BatchJobItem, message: str) -> dict[str, Any]:
        return {
            "candidate_id": item.candidate_id,
            "candidate_name": item.candidate_name,
            "error": message,
            "status": "FAILED",
        }


def process_batch_job(batch_job_id: str) -> dict[str, str | int]:
    """RQ coordinator that submits each candidate to the normal per-CV processing queue."""
    record = BatchJobRepository.get(batch_job_id)
    if record is None:
        raise LookupError(f"Batch job '{batch_job_id}' was not found.")
    if record.stage == "cv_jobs_queued":
        return {"batch_job_id": batch_job_id, "queued": record.total}
    BatchJobRepository.update(batch_job_id, state="PROCESSING", stage="candidate_discovery", message="Loading batch candidates.")
    try:
        session_factory = cast(Any, MssqlReadSession)
        if session_factory is None:
            raise RuntimeError("MSSQL is unavailable for batch candidate discovery.")
        with session_factory() as db:
            stmt = (
                select(RecruitCandidateMst)
                .where(RecruitCandidateMst.CandidateIsActive == True)
                .where(RecruitCandidateMst.CandidateCVFileName.isnot(None))
                .limit(record.limit)
            )
            candidates = db.execute(stmt).scalars().all()

        if not candidates:
            BatchJobRepository.update(
                batch_job_id,
                state="COMPLETED",
                stage="complete",
                progress=100,
                message="No candidates with CVs found.",
                completed_at=datetime.now(timezone.utc),
            )
            return {"batch_job_id": batch_job_id, "queued": 0}

        items: list[BatchJobItem] = []
        for candidate in candidates:
            candidate_id = int(candidate.CandidateID)
            candidate_name = " ".join(
                part.strip()
                for part in (candidate.CandidateFirstName, candidate.CandidateLastName)
                if isinstance(part, str) and part.strip()
            ) or f"Candidate {candidate_id}"
            filename = str(candidate.CandidateCVFileName)
            identity = resolve_cv_identity(filename, candidate_id=candidate_id)
            try:
                source = UploadService.load_reprocessable_upload(
                    storage_filename=filename,
                    original_filename=filename,
                    cv_key=identity.canonical_key,
                )
                if source is None:
                    raise FileNotFoundError("CV file is missing.")
                retained = UploadService.persist_bytes(
                    filename=source.safe_filename,
                    content=source.content,
                    storage_key=identity.canonical_key,
                    declared_content_type=source.detected_content_type,
                )
                submission = ProcessingQueueService.submit_upload(
                    cv_key=identity.canonical_key,
                    content_hash=retained.content_hash,
                    filename=retained.safe_filename,
                    storage_filename=retained.storage_filename,
                    content_type=retained.detected_content_type,
                    candidate_id=candidate_id,
                    source_candidate_id=candidate_id,
                )
                items.append(
                    BatchJobItem(
                        candidate_id=candidate_id,
                        candidate_name=candidate_name,
                        filename=filename,
                        cv_key=identity.canonical_key,
                        processing_job_id=submission.record.job_id,
                    )
                )
            except Exception as exc:
                logger.warning(f"Could not queue batch candidate {candidate_id}: {type(exc).__name__}")
                items.append(
                    BatchJobItem(
                        candidate_id=candidate_id,
                        candidate_name=candidate_name,
                        filename=filename,
                        cv_key=identity.canonical_key,
                        error="CV file could not be validated or queued.",
                    )
                )
            BatchJobRepository.update(
                batch_job_id,
                state="PROCESSING",
                stage="candidate_enqueue",
                total=len(candidates),
                items=items,
                progress=min(20, int(len(items) * 20 / len(candidates))),
                message=f"Queued {len(items)} of {len(candidates)} candidate CVs.",
            )

        BatchJobRepository.update(
            batch_job_id,
            state="PROCESSING",
            stage="cv_jobs_queued",
            total=len(items),
            items=items,
            progress=20,
            message=f"Queued {len(items)} candidate CVs for standard processing.",
        )
        return {"batch_job_id": batch_job_id, "queued": len(items)}
    except Exception:
        BatchJobRepository.update(
            batch_job_id,
            state="FAILED",
            stage="failed",
            progress=100,
            error="Batch candidate discovery failed.",
            message="Batch processing failed before CV jobs were queued.",
            completed_at=datetime.now(timezone.utc),
        )
        raise
