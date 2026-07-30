from typing import Any
from pydantic import BaseModel, Field


class CandidateSearchRequest(BaseModel):
    query: str | None = Field(
        None,
        description="Natural language search query (e.g. 'Senior Python developer with cloud deployment and microservices')",
    )
    department: str | None = Field(None, description="Filter by department name")
    department_id: int | None = Field(None, description="Filter by department ID")
    min_experience: float | None = Field(None, description="Minimum total experience years")
    max_experience: float | None = Field(None, description="Maximum total experience years")
    location: str | None = Field(None, description="Filter by location name")
    skills: list[str] | None = Field(None, description="List of required skills")
    education: str | None = Field(None, description="Filter by education background")
    status: str | None = Field(None, description="Filter candidate status")
    limit: int = Field(50, ge=1, le=200, description="Maximum number of candidate results to return")
    min_similarity: float | None = Field(
        None, ge=0.0, le=1.0, description="Minimum vector similarity threshold"
    )


class CandidateSearchResultItem(BaseModel):
    id: str = Field(..., description="Candidate record ID / cv_key")
    filename: str = Field(..., description="Original CV filename")
    full_name: str | None = Field(None, description="Candidate full name")
    email: str | None = Field(None, description="Candidate email address")
    phone: str | None = Field(None, description="Candidate phone number")
    parsed_at: str | None = Field(None, description="Timestamp when candidate CV was parsed")
    page_count: int = Field(1, description="Page count of parsed CV")
    is_scanned: bool = Field(False, description="Whether document was scanned PDF")
    ocr_applied: bool = Field(False, description="Whether OCR was applied")
    primary_department: str | None = Field(None, description="Primary matching department")
    similarity_score: float | None = Field(
        None, description="Semantic vector similarity score (0.0 to 1.0) when query is supplied"
    )
    search_mode: str = Field("keyword", description="Search execution mode: 'semantic' or 'keyword'")
    best_match: dict[str, Any] | None = Field(None, description="Best job match evaluation summary")


class CandidateSearchResponse(BaseModel):
    total_found: int = Field(..., description="Total candidate results matching search and filters")
    search_mode: str = Field(..., description="Search mode used: 'semantic' or 'keyword'")
    query: str | None = Field(None, description="Natural language search query applied")
    candidates: list[CandidateSearchResultItem] = Field(
        default_factory=list, description="List of ranked candidate search items"
    )
