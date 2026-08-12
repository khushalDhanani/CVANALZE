from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LLMExecutionTrace(BaseModel):
    """Privacy-safe execution lineage. Raw prompts, CV text, and model reasoning are forbidden."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = ""
    correlation_id: str = ""
    operation: str
    model_identifier_hash: str
    model_digest: str = ""
    prompt_version: str = ""
    prompt_hash: str = ""
    source_hash: str = ""
    source_freshness: str = "unknown"
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    duration_ms: float = Field(default=0.0, ge=0.0)
    inference_ms: float = Field(default=0.0, ge=0.0)
    validation_ms: float = Field(default=0.0, ge=0.0)
    attempts: int = Field(default=0, ge=0)
    completion_reason: str = ""
    cache_status: str = "MISS"
    validation_status: str = "NOT_RUN"
    fallback_used: bool = False
    error_class: str = ""
    quality_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GroundedAssertion(BaseModel):
    claim: str
    evidence_reference: str
    source_hash: str
    confidence: float = Field(ge=0.0, le=1.0)
