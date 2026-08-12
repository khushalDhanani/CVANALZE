from __future__ import annotations
from pydantic import BaseModel, Field


class MergedInterval(BaseModel):
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    duration_days: int = Field(default=0)


class WorkExperienceCalculationSummary(BaseModel):
    gross_experience_days: int = Field(default=0)
    unique_experience_days: int = Field(default=0)
    full_time_experience_days: int = Field(default=0)
    part_time_experience_days: int = Field(default=0)
    contract_experience_days: int = Field(default=0)
    temporary_experience_days: int = Field(default=0)
    apprenticeship_experience_days: int = Field(default=0)
    internship_experience_days: int = Field(default=0)
    freelance_experience_days: int = Field(default=0)
    self_employed_experience_days: int = Field(default=0)
    completed_years: int = Field(default=0)
    remaining_months: int = Field(default=0)
    remaining_days: int = Field(default=0)
    experience_display: str = Field(default="0 years 0 months")
    merged_intervals: list[MergedInterval] = Field(default_factory=list)
