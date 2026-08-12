from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, JSON, Sequence, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import PostgresAppBase


_enqueue_sequence = Sequence("cv_processing_jobs_enqueue_seq")


class CVProcessingJob(PostgresAppBase):
    __tablename__ = "cv_processing_jobs"

    job_id = Column(String(80), primary_key=True)
    enqueue_sequence = Column(BigInteger, _enqueue_sequence, nullable=False, server_default=_enqueue_sequence.next_value(), index=True)
    cv_key = Column(String(255), nullable=False, index=True)
    content_hash = Column(String(64), nullable=False)
    filename = Column(String(255), nullable=False)
    storage_filename = Column(String(255), nullable=False)
    content_type = Column(String(160), nullable=True)
    candidate_id = Column(String(255), nullable=True, index=True)
    source_candidate_id = Column(BigInteger, nullable=True)
    cv_id = Column(String(255), nullable=True, index=True)
    parser_version = Column(String(80), nullable=False)
    schema_version = Column(String(80), nullable=False)
    state = Column(String(32), nullable=False, index=True)
    progress = Column(Integer, nullable=False, default=10)
    stage = Column(String(120), nullable=False, default="queued")
    message = Column(Text, nullable=False, default="CV processing is queued.")
    execution_mode = Column(String(32), nullable=False)
    rq_job_id = Column(String(160), nullable=True, unique=True)
    attempt = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=1)
    enqueue_count = Column(Integer, nullable=False, default=0)
    force_reprocess = Column(Boolean, nullable=False, default=False)
    outcome = Column(String(40), nullable=True)
    error = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
