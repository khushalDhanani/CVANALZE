from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

EmploymentEntityResolution = Literal[
    "PARENT_EMPLOYMENT",
    "INTERNAL_ROLE",
    "DEPUTATION",
    "PROMOTION_TRANSFER",
    "INDEPENDENT_CONCURRENT_ROLE",
    "DUPLICATE",
    "INVALID_HEADING",
]


class ExperienceTimelineNode(BaseModel):
    record_id: str
    company: str
    job_title: str
    employment_type: str = "full_time"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    duration_months: int = 0
    precision: str = "day"
    date_confidence: Literal["EXACT", "MONTH_ONLY", "YEAR_ONLY", "UNKNOWN"] = "MONTH_ONLY"
    responsibilities: list[str] = Field(default_factory=list)


class ChildAssignment(BaseModel):
    assignment_id: str
    title_or_subrole: str
    assignment_type: Literal["DEPUTATION", "PROMOTION", "TRANSFER", "INTERNAL_ASSIGNMENT", "SUB_ROLE"] = "SUB_ROLE"
    entity_resolution: EmploymentEntityResolution = "INTERNAL_ROLE"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    details: list[str] = Field(default_factory=list)


class CanonicalJob(BaseModel):
    job_id: str
    parent_company: str
    primary_title: str
    employment_type: str = "full_time"
    entity_resolution: EmploymentEntityResolution = "PARENT_EMPLOYMENT"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    duration_months: int = 0
    date_confidence: Literal["EXACT", "MONTH_ONLY", "YEAR_ONLY", "UNKNOWN"] = "MONTH_ONLY"
    responsibilities: list[str] = Field(default_factory=list)
    child_assignments: list[ChildAssignment] = Field(default_factory=list)


class ExperienceGap(BaseModel):
    gap_id: str
    category: Literal["EMPLOYMENT_GAP"] = "EMPLOYMENT_GAP"
    coverage_status: Literal[
        "UNEXPLAINED",
        "EDUCATION_COVERED",
        "FREELANCE_COVERED",
        "CONTRACT_COVERED",
        "CAREER_TRANSITION",
        "TIMELINE_UNCERTAINTY",
    ] = "UNEXPLAINED"
    boundary_reliability: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_days: int = 0
    duration_months: float = 0.0
    preceding_role: Optional[str] = None
    following_role: Optional[str] = None
    description: str = ""
    hr_review_indicator: bool = False
    hr_review_reason: Optional[str] = None


class ConcurrentRoleCluster(BaseModel):
    cluster_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    duration_months: int = 0
    roles_count: int = 0
    child_nodes: list[ExperienceTimelineNode] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    event_id: str
    event_type: Literal[
        "EMPLOYMENT_PERIOD",
        "CONCURRENT_CLUSTER",
        "EMPLOYMENT_GAP",
        "COVERED_GAP",
        "TIMELINE_UNCERTAINTY",
    ]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    duration_months: float = 0.0
    node: Optional[ExperienceTimelineNode] = None
    cluster: Optional[ConcurrentRoleCluster] = None
    gap: Optional[ExperienceGap] = None


class ExperienceTimelineSummary(BaseModel):
    total_verified_years: float = 0.0
    gross_display: str = "0 years 0 months"
    timeline_start_date: Optional[str] = None
    timeline_end_date: Optional[str] = None
    has_current_employment: bool = False
    concurrent_roles_count: int = 0
    total_employment_gaps_count: int = 0
    unexplained_gaps_count: int = 0
    significant_gaps_count: int = 0
    total_gap_duration_months: float = 0.0
    analysis_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    timeline_uncertainty_score: float = Field(default=0.0, ge=0.0, le=1.0)
    hr_review_required: bool = False
    hr_observations: list[str] = Field(default_factory=list)


class ExperienceGapAnalysis(BaseModel):
    summary: ExperienceTimelineSummary = Field(default_factory=ExperienceTimelineSummary)
    detected_gaps: list[ExperienceGap] = Field(default_factory=list)
    canonical_jobs: list[CanonicalJob] = Field(default_factory=list)
    timeline_nodes: list[ExperienceTimelineNode] = Field(default_factory=list)
    undated_nodes: list[ExperienceTimelineNode] = Field(default_factory=list)
    timeline_events: list[TimelineEvent] = Field(default_factory=list)
    hr_review_indicators: list[str] = Field(default_factory=list)
