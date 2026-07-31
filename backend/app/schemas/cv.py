from typing import Any

from pydantic import BaseModel, Field

from app.schemas.match import CandidateMatchAnalysis
from app.schemas.profile import DynamicCandidateProfile


class CVProcessingResponse(BaseModel):
    message: str = Field(..., description="Status message")
    cv_key: str = Field(..., description="Unique CV execution ID")
    status: str = Field(default="processing", description="Current status")
    progress: int | None = Field(default=None, description="Progress percentage (0-100)")
    stage: str | None = Field(default=None, description="Current processing stage")
    failed_step: str | None = Field(default=None, description="Step where the pipeline failed")
    error_details: str | None = Field(default=None, description="Detailed stack trace or technical error info")


class CVUploadResponse(BaseModel):
    id: str = Field(..., description="Unique scan execution ID")
    scan_id: str = Field(..., description="Unique scan execution ID (alias for id)")
    parsed_at: str | None = Field(None, description="ISO timestamp of parsing (alias for scanned_at)")
    filename: str = Field(..., description="Uploaded CV filename")
    content_type: str | None = Field(None, description="MIME content type")
    characters: int = Field(
        ..., description="Total character count of extracted Markdown text"
    )
    page_count: int = Field(..., description="Total number of pages in the document")
    is_scanned: bool = Field(
        ...,
        description="Indicates whether the document was detected as scanned/image-heavy",
    )
    ocr_applied: bool = Field(
        ..., description="Indicates whether local OCR was executed"
    )
    text: str = Field(..., description="Clean extracted Markdown text content")
    markdown: str = Field(..., description="Clean extracted Markdown text content")
    structured_doc: dict[str, Any] | None = Field(
        default=None, description="Docling structured document JSON model"
    )
    match_analysis: CandidateMatchAnalysis = Field(
        ..., description="Job matching analysis, scores, and candidate classifications"
    )
    result_file_path: str | None = Field(
        None, description="Path to saved JSON extraction result file"
    )
    candidate_id: str | None = Field(None, description="Candidate or User ID")
    cv_id: str | None = Field(None, description="Unique CV ID")
    cv_hash: str | None = Field(None, description="SHA-256 hash of CV source content")
    parser_version: str | None = Field(None, description="Document parser version")
    schema_version: str | None = Field(None, description="Extraction schema version")
    created_at: str | None = Field(None, description="ISO timestamp of initial creation")
    updated_at: str | None = Field(None, description="ISO timestamp of last update")
    status: str | None = Field(
        None,
        description="Processing status: CACHE_HIT, NEW_CV, CV_CHANGED, SCHEMA_CHANGED, REPROCESSED",
    )
    dynamic_profile: DynamicCandidateProfile | None = Field(
        None, description="Dynamically extracted candidate profile from LLM analysis."
    )
    quality_metrics: dict[str, Any] | None = Field(
        None, description="Extraction quality metrics (pages, words, completeness score, sections detected)"
    )
    resume_json: dict[str, Any] | None = Field(
        None, description="Normalized structured Resume JSON parsed from extracted text"
    )
    full_name: str | None = Field(None, description="Extracted candidate full name")
    candidate_name: str | None = Field(None, description="Extracted candidate name")
    email: str | None = Field(None, description="Extracted candidate email address")
    phone: str | None = Field(None, description="Extracted candidate phone number")
    location: str | None = Field(None, description="Extracted candidate location")
    job_title: str | None = Field(None, description="Extracted candidate job title")
    company_name: str | None = Field(None, description="Extracted candidate company name")
    name_confidence: float | None = Field(None, description="Name extraction confidence score (0.0 to 1.0)")
    name_confidence_tier: str | None = Field(None, description="Name confidence tier label (HIGH, MEDIUM, LOW)")
    location_confidence_tier: str | None = Field(None, description="Location confidence tier label (HIGH, MEDIUM, LOW)")
    job_title_confidence_tier: str | None = Field(None, description="Job title confidence tier label (HIGH, MEDIUM, LOW)")
    company_name_confidence_tier: str | None = Field(None, description="Company name confidence tier label (HIGH, MEDIUM, LOW)")
    field_confidence: dict[str, float | None] | None = Field(None, description="Per-field confidence raw scores")
    field_confidence_tiers: dict[str, str | None] | None = Field(None, description="Per-field confidence tier labels (HIGH, MEDIUM, LOW)")
    name_extraction_source: str | None = Field(None, description="Source of candidate name extraction")




class CVMatchRequest(BaseModel):
    cv_text: str = Field(
        ..., description="Extracted Markdown or plain text of candidate CV"
    )
