from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, Identity, Integer, JSON, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import PostgresAppBase


class LLMExecutionTraceRecord(PostgresAppBase):
    __tablename__ = "llm_execution_traces"

    id = Column(BigInteger, Identity(), primary_key=True)
    request_id = Column(String(128), nullable=False, default="", index=True)
    correlation_id = Column(String(128), nullable=False, default="", index=True)
    operation = Column(String(80), nullable=False, index=True)
    model_identifier_hash = Column(String(64), nullable=False)
    model_digest = Column(String(128), nullable=False, default="")
    prompt_version = Column(String(80), nullable=False, default="")
    prompt_hash = Column(String(64), nullable=False, default="")
    source_hash = Column(String(64), nullable=False, default="", index=True)
    source_freshness = Column(String(40), nullable=False, default="unknown")
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    duration_ms = Column(Float, nullable=False, default=0.0)
    inference_ms = Column(Float, nullable=False, default=0.0)
    validation_ms = Column(Float, nullable=False, default=0.0)
    attempts = Column(Integer, nullable=False, default=0)
    completion_reason = Column(String(40), nullable=False, default="")
    cache_status = Column(String(20), nullable=False, default="MISS")
    validation_status = Column(String(40), nullable=False, default="NOT_RUN")
    fallback_used = Column(Boolean, nullable=False, default=False)
    error_class = Column(String(120), nullable=False, default="")
    quality_metadata = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
