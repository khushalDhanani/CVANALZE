from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class BatchJobItem(BaseModel):
    candidate_id: int
    candidate_name: str
    filename: str
    cv_key: str | None = None
    processing_job_id: str | None = None
    error: str | None = None


class BatchJobRecord(BaseModel):
    batch_job_id: str
    state: str = "QUEUED"
    stage: str = "queued"
    message: str = "Batch processing is queued."
    limit: int
    progress: int = Field(default=0, ge=0, le=100)
    processed: int = 0
    total: int = 0
    items: list[BatchJobItem] = Field(default_factory=list)
    matches: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    def to_response(self) -> dict[str, Any]:
        return {
            "batch_job_id": self.batch_job_id,
            "status": self.state,
            "stage": self.stage,
            "message": self.message,
            "progress": self.progress,
            "processed": self.processed,
            "total": self.total,
            "matches": self.matches,
            "error": self.error,
        }
