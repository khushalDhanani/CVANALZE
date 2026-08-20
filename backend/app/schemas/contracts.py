from __future__ import annotations
from collections.abc import Mapping
from datetime import timezone, datetime
from enum import Enum
from typing import Any, Generic, TypeVar, Optional

from pydantic import BaseModel, Field, field_validator
from app.core.rule_config_manager import RuleConfigManager

T = TypeVar("T")


class EvidenceStatus(str, Enum):
    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"
    CONFLICTING = "CONFLICTING"
    NOT_FOUND = "NOT_FOUND"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"
    SYSTEM_UNAVAILABLE = "SYSTEM_UNAVAILABLE"


class EvidenceRef(BaseModel):
    source_section: str = Field(default="general")
    raw_quote: str = Field(default="")
    provenance: str = Field(default="VERIFIED_CV")
    confidence_score: float = Field(default=1.0)
    start_char: int | None = None
    end_char: int | None = None


class EvidenceResult(BaseModel, Generic[T]):
    value: T | None = None
    status: EvidenceStatus = EvidenceStatus.NOT_FOUND
    confidence: float | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    source: str = Field(default="deterministic")
    policy_id: str | None = None
    policy_version: str | None = None
    model_version: str | None = None
    taxonomy_version: str | None = None
    degraded_mode: bool = False

    @classmethod
    def not_found(
        cls,
        *,
        source: str = "deterministic",
        policy_id: str | None = None,
        policy_version: str | None = None,
        model_version: str | None = None,
        taxonomy_version: str | None = None,
        degraded_mode: bool = False,
    ) -> EvidenceResult[T]:
        return cls(
            status=EvidenceStatus.NOT_FOUND,
            source=source,
            policy_id=policy_id,
            policy_version=policy_version,
            model_version=model_version,
            taxonomy_version=taxonomy_version,
            degraded_mode=degraded_mode,
        )

    @classmethod
    def not_assessable(
        cls,
        reason: str,
        *,
        source: str = "deterministic",
        policy_id: str | None = None,
        policy_version: str | None = None,
        model_version: str | None = None,
        taxonomy_version: str | None = None,
        degraded_mode: bool = False,
    ) -> EvidenceResult[T]:
        return cls(
            status=EvidenceStatus.NOT_ASSESSABLE,
            source=source,
            policy_id=policy_id,
            policy_version=policy_version,
            model_version=model_version,
            taxonomy_version=taxonomy_version,
            degraded_mode=degraded_mode,
            evidence=[EvidenceRef(raw_quote=f"NOT_ASSESSABLE: {reason}", confidence_score=0.0, provenance="NO_EVIDENCE")],
        )

    @classmethod
    def verified(
        cls,
        value: T,
        confidence: float = 1.0,
        *,
        evidence: list[EvidenceRef] | None = None,
        source: str = "deterministic",
        policy_id: str | None = None,
        policy_version: str | None = None,
        model_version: str | None = None,
        taxonomy_version: str | None = None,
        degraded_mode: bool = False,
    ) -> EvidenceResult[T]:
        return cls(
            value=value,
            status=EvidenceStatus.VERIFIED,
            confidence=confidence,
            evidence=evidence or [],
            source=source,
            policy_id=policy_id,
            policy_version=policy_version,
            model_version=model_version,
            taxonomy_version=taxonomy_version,
            degraded_mode=degraded_mode,
        )

    @classmethod
    def inferred(
        cls,
        value: T,
        confidence: float = 0.7,
        *,
        evidence: list[EvidenceRef] | None = None,
        source: str = "llm",
        policy_id: str | None = None,
        policy_version: str | None = None,
        model_version: str | None = None,
        taxonomy_version: str | None = None,
        degraded_mode: bool = False,
    ) -> EvidenceResult[T]:
        return cls(
            value=value,
            status=EvidenceStatus.INFERRED,
            confidence=confidence,
            evidence=evidence or [],
            source=source,
            policy_id=policy_id,
            policy_version=policy_version,
            model_version=model_version,
            taxonomy_version=taxonomy_version,
            degraded_mode=degraded_mode,
        )

    @classmethod
    def conflicting(
        cls,
        reason: str,
        *,
        value: T | None = None,
        source: str = "deterministic",
        policy_id: str | None = None,
        policy_version: str | None = None,
        model_version: str | None = None,
        taxonomy_version: str | None = None,
        degraded_mode: bool = False,
    ) -> EvidenceResult[T]:
        return cls(
            value=value,
            status=EvidenceStatus.CONFLICTING,
            confidence=0.0,
            source=source,
            policy_id=policy_id,
            policy_version=policy_version,
            model_version=model_version,
            taxonomy_version=taxonomy_version,
            degraded_mode=degraded_mode,
            evidence=[EvidenceRef(raw_quote=f"CONFLICTING: {reason}", confidence_score=0.0, provenance="CONFLICTING_EVIDENCE")],
        )

    @classmethod
    def not_applicable(
        cls,
        *,
        source: str = "deterministic",
        policy_id: str | None = None,
        policy_version: str | None = None,
        model_version: str | None = None,
        taxonomy_version: str | None = None,
    ) -> EvidenceResult[T]:
        return cls(
            status=EvidenceStatus.NOT_APPLICABLE,
            source=source,
            policy_id=policy_id,
            policy_version=policy_version,
            model_version=model_version,
            taxonomy_version=taxonomy_version,
            degraded_mode=False,
        )

    @classmethod
    def system_unavailable(
        cls,
        reason: str = "System service degraded or offline",
        *,
        policy_id: str | None = None,
        policy_version: str | None = None,
        model_version: str | None = None,
        taxonomy_version: str | None = None,
    ) -> EvidenceResult[T]:
        return cls(
            status=EvidenceStatus.SYSTEM_UNAVAILABLE,
            confidence=0.0,
            source="system",
            policy_id=policy_id,
            policy_version=policy_version,
            model_version=model_version,
            taxonomy_version=taxonomy_version,
            degraded_mode=True,
            evidence=[EvidenceRef(raw_quote=f"SYSTEM_UNAVAILABLE: {reason}", confidence_score=0.0, provenance="SYSTEM_DEGRADED")],
        )



class AccessTier(str, Enum):
    PUBLIC = "public"
    RECRUITER = "recruiter"
    ADMINISTRATOR = "administrator"


class JobState:
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    COMPLETED_DEGRADED = "COMPLETED_DEGRADED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class ProcessingOutcome(str, Enum):
    NEW_CV = "NEW_CV"
    REPROCESSED = "REPROCESSED"
    CACHE_HIT = "CACHE_HIT"


class ProcessingExecutionMode(str, Enum):
    PENDING = "PENDING"
    RQ = "RQ"
    DEVELOPMENT_FALLBACK = "DEVELOPMENT_FALLBACK"


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    UNSUPPORTED_FILE = "UNSUPPORTED_FILE"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    CONFIGURATION_UNAVAILABLE = "CONFIGURATION_UNAVAILABLE"
    PROMPT_UNAVAILABLE = "PROMPT_UNAVAILABLE"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    WORKER_LOST = "WORKER_LOST"
    JOB_STUCK = "JOB_STUCK"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    ANALYSIS_INVALID = "ANALYSIS_INVALID"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


LEGACY_JOB_STATE_ALIASES: dict[str, str] = {
    "QUEUED": JobState.QUEUED,
    "PROCESSING": JobState.PROCESSING,
    "IN_PROGRESS": JobState.PROCESSING,
    "CV_CHANGED": JobState.PROCESSING,
    "SCHEMA_CHANGED": JobState.PROCESSING,
    "RETRYING": JobState.RETRYING,
    "COMPLETED": JobState.COMPLETED,
    "COMPLETED_DEGRADED": JobState.COMPLETED_DEGRADED,
    "NEW_CV": JobState.COMPLETED,
    "REPROCESSED": JobState.COMPLETED,
    "CACHE_HIT": JobState.COMPLETED,
    "FAILED": JobState.FAILED,
    "ERROR": JobState.FAILED,
    "CANCELLED": JobState.CANCELLED,
    "CANCELED": JobState.CANCELLED,
}


def normalize_job_state(
    status: str | None,
    *,
    progress: int | None = None,
    is_complete: bool | None = None,
) -> str:
    normalized = str(status or "").strip().upper()
    if normalized in ("FAILED", "ERROR"):
        return JobState.FAILED
    if normalized in ("CANCELLED", "CANCELED"):
        return JobState.CANCELLED
    if normalized == JobState.COMPLETED_DEGRADED:
        return JobState.COMPLETED_DEGRADED
    if is_complete is True:
        return JobState.COMPLETED
    if progress == 100:
        return JobState.COMPLETED
    return LEGACY_JOB_STATE_ALIASES.get(normalized, JobState.UNKNOWN)


class CanonicalError(BaseModel):
    code: ErrorCode
    message: str
    request_id: str | None = None
    correlation_id: str | None = None
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: CanonicalError
    detail: str | None = None

    def to_legacy_detail(self) -> dict[str, str]:
        return {"detail": self.error.message}


class JobStateResponse(BaseModel):
    job_id: str
    state: str
    
    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        allowed = RuleConfigManager.get_config().workflow.allowed_job_states
        if v not in allowed:
            raise ValueError(f"Invalid job state '{v}'. Must be one of {allowed}")
        return v
    progress: int = Field(default=0, ge=0, le=100)
    stage: str | None = None
    message: str = ""
    outcome: ProcessingOutcome | None = None
    error: CanonicalError | None = None

    @classmethod
    def from_legacy(cls, payload: Mapping[str, Any]) -> "JobStateResponse":
        raw_status = str(payload.get("status") or "")
        raw_outcome = str(payload.get("original_status") or "").upper()
        try:
            outcome = ProcessingOutcome(raw_outcome)
        except ValueError:
            outcome = None
        try:
            progress = int(payload.get("progress") or 0)
        except (TypeError, ValueError):
            progress = 0
        progress = min(100, max(0, progress))
        state = normalize_job_state(
            raw_status,
            progress=progress,
            is_complete=payload.get("is_complete"),
        )
        error = None
        if state == JobState.FAILED:
            error = CanonicalError(
                code=ErrorCode.PROCESSING_FAILED,
                message=str(payload.get("message") or payload.get("error") or "CV processing failed."),
                retryable=True,
            )
        return cls(
            job_id=str(payload.get("cv_key") or payload.get("scan_id") or payload.get("id") or ""),
            state=state,
            progress=progress,
            stage=payload.get("stage"),
            message=str(payload.get("message") or ""),
            outcome=outcome,
            error=error,
        )

    def to_legacy_processing(self) -> dict[str, Any]:
        legacy_status = {
            JobState.QUEUED: "processing",
            JobState.PROCESSING: "processing",
            JobState.RETRYING: "processing",
            JobState.COMPLETED: "COMPLETED",
            JobState.COMPLETED_DEGRADED: "COMPLETED_DEGRADED",
            JobState.FAILED: "FAILED",
            JobState.CANCELLED: "CANCELLED",
            JobState.UNKNOWN: "processing",
        }[self.state]
        payload: dict[str, Any] = {
            "message": self.message,
            "cv_key": self.job_id,
            "status": legacy_status,
            "progress": self.progress,
            "stage": self.stage,
        }
        if self.error:
            payload["failed_step"] = self.stage
            payload["error_details"] = None
        return payload


class ProcessingJobRecord(BaseModel):
    job_id: str
    cv_key: str
    content_hash: str
    filename: str
    storage_filename: str
    correlation_id: str | None = None
    original_filename: str | None = None
    display_filename: str | None = None
    content_type: str | None = None
    candidate_id: str | None = None
    source_candidate_id: int | None = None
    cv_id: str | None = None
    parser_version: str
    schema_version: str
    state: str = JobState.QUEUED
    progress: int = Field(default=10, ge=0, le=100)
    stage: str = "queued"
    message: str = "CV processing is queued."
    execution_mode: ProcessingExecutionMode = ProcessingExecutionMode.PENDING
    rq_job_id: str | None = None
    attempt: int = 0
    max_attempts: int = 1
    enqueue_count: int = 0
    force_reprocess: bool = False
    outcome: ProcessingOutcome | None = None
    error: CanonicalError | None = None
    enqueue_sequence: int | None = None
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    completed_at: datetime | None = None

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        allowed = RuleConfigManager.get_config().workflow.allowed_job_states
        if v not in allowed:
            raise ValueError(f"Invalid job state '{v}'. Must be one of {allowed}")
        return v
