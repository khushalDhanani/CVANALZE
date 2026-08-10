from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from app.core.cache import processing_job_cache_manager
from app.core.config import settings
from app.schemas.batch import BatchJobRecord


class BatchJobRepository:
    _lock = threading.RLock()

    @classmethod
    def get(cls, batch_job_id: str) -> BatchJobRecord | None:
        payload = processing_job_cache_manager.get(f"batch_{batch_job_id}")
        if not isinstance(payload, dict):
            return None
        try:
            return BatchJobRecord.model_validate(payload)
        except Exception:
            return None

    @classmethod
    def save(cls, record: BatchJobRecord) -> BatchJobRecord:
        persisted = record.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        with cls._lock:
            processing_job_cache_manager.set(
                f"batch_{persisted.batch_job_id}",
                persisted.model_dump(mode="json"),
                ttl=settings.PROCESSING_JOB_TTL_SECONDS,
            )
        return persisted

    @classmethod
    def update(cls, batch_job_id: str, **updates: Any) -> BatchJobRecord:
        with cls._lock:
            record = cls.get(batch_job_id)
            if record is None:
                raise LookupError(f"Batch job '{batch_job_id}' was not found.")
            return cls.save(record.model_copy(update=updates))
