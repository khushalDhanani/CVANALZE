from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

from app.schemas.work_experience_calculation import WorkExperienceCalculationSummary


class WorkExperienceConfig(BaseModel):
    include_full_time: bool = True
    include_part_time: bool = True
    include_contract: bool = True
    include_temporary: bool = True
    include_freelance: bool = True
    include_self_employed: bool = True
    include_apprenticeship: bool = True
    include_internship: bool = True
    include_training: bool = False
    include_volunteer: bool = False
    include_unknown: bool = False
    merge_overlapping_periods: bool = True
    merge_adjacent_intervals: bool = True
    year_only_start_policy: Literal["manual_review", "exclude", "include"] = "manual_review"
    year_only_end_policy: Literal["manual_review", "exclude", "include"] = "manual_review"
    month_only_start_policy: Literal["first_day"] = "first_day"
    month_only_end_policy: Literal["last_day"] = "last_day"
    gap_threshold_days: int = Field(default=60, ge=1, description="Minimum days of employment hiatus to classify as an employment gap (default 60 days)")
    minimum_record_confidence: float = Field(default=0.60, ge=0.0, le=1.0)
    human_review_threshold: float = Field(default=0.75, ge=0.0, le=1.0)


class WorkExperienceExtractionRequest(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    ocr_text: str = Field(..., min_length=1, max_length=100000)
    reference_date: str = Field(..., description="YYYY-MM-DD format reference date")
    candidate_country: Optional[str] = None
    preferred_date_format: Literal["AUTO", "DD/MM/YYYY", "MM/DD/YYYY"] = "AUTO"
    config: WorkExperienceConfig = Field(default_factory=WorkExperienceConfig)


class WorkExperienceRecord(BaseModel):
    record_id: str
    original_text: str
    job_title_original: str
    job_title_normalized: str
    company_name_original: str
    company_name_normalized: str
    location: Optional[str] = None
    employment_type: Literal[
        "full_time",
        "part_time",
        "contract",
        "temporary",
        "freelance",
        "self_employed",
        "apprenticeship",
        "internship",
        "training",
        "volunteer",
        "unknown",
    ]
    start_date_original: str
    start_date_normalized: Optional[str] = None
    start_date_precision: Literal["day", "month", "year", "unknown"]
    end_date_original: str
    end_date_normalized: Optional[str] = None
    calculation_end_date: Optional[str] = None
    end_date_precision: Literal["day", "month", "year", "unknown"]
    is_current: bool
    estimated_start_date: bool
    estimated_end_date: bool
    include_in_experience: bool
    exclusion_reason: Optional[str] = None
    confidence: float
    requires_review: bool
    warnings: list[str] = Field(default_factory=list)
    review_reason_codes: list[str] = Field(default_factory=list)


class DuplicateRecord(BaseModel):
    kept_record_id: str
    duplicate_record_id: str
    duplicate_score: float
    matching_fields: list[str]
    reason: str


class CurrentEmployer(BaseModel):
    record_id: str
    company_name: str
    job_title: str
    start_date: Optional[str] = None


class CurrentEmployment(BaseModel):
    is_currently_employed: bool = False
    current_job_count: int = 0
    current_employers: list[CurrentEmployer] = Field(default_factory=list)


class ReviewReason(BaseModel):
    code: str
    record_id: Optional[str] = None
    message: str


class WorkExperienceExtractionMetadata(BaseModel):
    prompt_version: str
    calculation_version: str
    llm_model: str
    cache_hit: bool
    processing_time_ms: int


class WorkExperienceExtractionResponse(BaseModel):
    candidate_id: str
    reference_date: str
    extraction_status: Literal["success", "partial", "failed"]
    detected_date_pattern: str
    current_employment: CurrentEmployment
    experience_summary: WorkExperienceCalculationSummary
    employment_records: list[WorkExperienceRecord]
    duplicate_records: list[DuplicateRecord]
    unresolved_employment_text: list[str]
    global_warnings: list[str]
    review_reasons: list[ReviewReason]
    overall_confidence: float
    requires_human_review: bool
    metadata: WorkExperienceExtractionMetadata
