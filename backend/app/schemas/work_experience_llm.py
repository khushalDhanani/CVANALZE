from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class LLMWorkExperienceRecord(BaseModel):
    original_text: str = Field(default="")
    job_title_original: str = Field(default="")
    job_title_normalized: str = Field(default="")
    company_name_original: str = Field(default="")
    company_name_normalized: str = Field(default="")
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
    ] = "unknown"
    start_date_original: str = Field(default="")
    start_date_normalized: Optional[str] = None
    start_date_precision: Literal["day", "month", "year", "unknown"] = "unknown"
    end_date_original: str = Field(default="")
    end_date_normalized: Optional[str] = None
    end_date_precision: Literal["day", "month", "year", "unknown"] = "unknown"
    is_current: bool = False
    confidence: float = Field(default=0.0)
    warnings: list[str] = Field(default_factory=list)


class LLMWorkExperienceExtraction(BaseModel):
    detected_date_pattern: Literal["DD/MM/YYYY", "MM/DD/YYYY", "mixed", "textual", "unknown"] = "unknown"
    employment_records: list[LLMWorkExperienceRecord] = Field(default_factory=list)
    unresolved_employment_text: list[str] = Field(default_factory=list)
    global_warnings: list[str] = Field(default_factory=list)
    overall_confidence: float = Field(default=0.0)
