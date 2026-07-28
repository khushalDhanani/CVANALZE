from typing import Any

from pydantic import BaseModel, Field

from app.schemas.match import CandidateMatchAnalysis
from app.schemas.profile import DynamicCandidateProfile


class CVProcessingResponse(BaseModel):
    message: str = Field(..., description="Status message")
    cv_key: str = Field(..., description="Unique CV execution ID")
    status: str = Field(default="processing", description="Current status")
    progress: int | None = Field(default=None, description="Progress percentage (0-100)")


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
    structured_doc: dict[str, Any] = Field(
        ..., description="Docling structured document JSON model"
    )
    match_analysis: CandidateMatchAnalysis = Field(
        ..., description="Job matching analysis, scores, and candidate classifications"
    )
    result_file_path: str = Field(
        ..., description="Path to saved JSON extraction result file"
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



class CVMatchRequest(BaseModel):
    cv_text: str = Field(
        ..., description="Extracted Markdown or plain text of candidate CV"
    )
