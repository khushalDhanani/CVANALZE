import hashlib
import threading
from datetime import UTC, datetime
from typing import Any

from app.core.cache import processing_job_cache_manager
from app.core.config import settings
from app.schemas.contracts import JobState, ProcessingJobRecord


class ProcessingJobRepository:
    """Persist canonical background-job records and their latest CV-key aliases."""

    _lock = threading.RLock()

    @staticmethod
    def build_job_id(cv_key: str, content_hash: str) -> str:
        identity = "|".join(
            (
                cv_key,
                content_hash,
                settings.EXTRACTION_PARSER_VERSION,
                settings.EXTRACTION_SCHEMA_VERSION,
            )
        )
        return f"cvjob_{hashlib.sha256(identity.encode('utf-8')).hexdigest()}"

    @classmethod
    def get(cls, job_id: str) -> ProcessingJobRecord | None:
        payload = processing_job_cache_manager.get(f"job_{job_id}")
        return cls._validate(payload)

    @classmethod
    def get_by_cv_key(cls, cv_key: str) -> ProcessingJobRecord | None:
        alias = hashlib.sha256(cv_key.encode("utf-8")).hexdigest()
        payload = processing_job_cache_manager.get(f"cv_{alias}")
        return cls._validate(payload)

    @classmethod
    def save(cls, record: ProcessingJobRecord) -> ProcessingJobRecord:
        persisted = record.model_copy(update={"updated_at": datetime.now(UTC)})
        payload = persisted.model_dump(mode="json")
        ttl = settings.PROCESSING_JOB_TTL_SECONDS
        alias = hashlib.sha256(persisted.cv_key.encode("utf-8")).hexdigest()
        with cls._lock:
            processing_job_cache_manager.set(f"job_{persisted.job_id}", payload, ttl=ttl)
            processing_job_cache_manager.set(f"cv_{alias}", payload, ttl=ttl)
        return persisted

    @classmethod
    def transition(
        cls,
        job_id: str,
        state: JobState,
        **updates: Any,
    ) -> ProcessingJobRecord:
        with cls._lock:
            record = cls.get(job_id)
            if record is None:
                raise LookupError(f"Processing job '{job_id}' was not found.")
            cls._assert_transition(record.state, state)
            now = datetime.now(UTC)
            if state == JobState.PROCESSING and record.started_at is None:
                updates.setdefault("started_at", now)
            if state in (JobState.COMPLETED, JobState.FAILED):
                updates.setdefault("completed_at", now)
            return cls.save(record.model_copy(update={"state": state, **updates}))

    @staticmethod
    def _validate(payload: Any) -> ProcessingJobRecord | None:
        if not isinstance(payload, dict):
            return None
        try:
            return ProcessingJobRecord.model_validate(payload)
        except Exception:
            return None

    @staticmethod
    def _assert_transition(current: JobState, target: JobState) -> None:
        allowed = {
            JobState.QUEUED: {
                JobState.QUEUED,
                JobState.PROCESSING,
                JobState.RETRYING,
                JobState.FAILED,
            },
            JobState.PROCESSING: {
                JobState.PROCESSING,
                JobState.RETRYING,
                JobState.COMPLETED,
                JobState.FAILED,
            },
            JobState.RETRYING: {
                JobState.RETRYING,
                JobState.PROCESSING,
                JobState.FAILED,
            },
            JobState.COMPLETED: {JobState.COMPLETED, JobState.QUEUED},
            JobState.FAILED: {JobState.FAILED, JobState.QUEUED},
            JobState.UNKNOWN: {JobState.QUEUED, JobState.FAILED},
        }
        if target not in allowed[current]:
            raise ValueError(f"Invalid processing-job transition: {current.value} -> {target.value}")
