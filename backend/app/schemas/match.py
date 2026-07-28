from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class RequirementTier(str, Enum):
    MANDATORY = "MANDATORY"
    PREFERRED = "PREFERRED"
    OPTIONAL = "OPTIONAL"


class RequirementStatus(str, Enum):
    SATISFIED = "SATISFIED"
    PARTIALLY_SATISFIED = "PARTIALLY_SATISFIED"
    FAILED = "FAILED"
    UNVERIFIED = "UNVERIFIED"


class DualEvidence(BaseModel):
    cv_evidence: str = Field(..., description="Extract/quote or verified fact from candidate CV")
    vacancy_evidence: str = Field(..., description="Target requirement description or text from vacancy")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class RequirementEvaluation(BaseModel):
    requirement_id: str = Field(..., description="Unique identifier for requirement item")
    description: str = Field(..., description="Text description of requirement")
    tier: RequirementTier = Field(..., description="Requirement classification tier")
    status: RequirementStatus = Field(..., description="Evaluation status of requirement")
    evidence: DualEvidence = Field(..., description="Supporting evidence from CV and Vacancy")
    failure_reason: str | None = Field(None, description="Detailed explanation if requirement failed or partially satisfied")


class MandatoryFailureDetails(BaseModel):
    requirement_id: str = Field(..., description="Identifier of failed mandatory requirement")
    description: str = Field(..., description="Requirement description")
    reason: str = Field(..., description="Explicit reason why mandatory requirement was not satisfied")
    score_impact: float = Field(default=0.0, description="Deduction or penalty applied to final score")


class JobMatchResult(BaseModel):
    job_id: str = Field(..., description="Unique job opening ID")
    job_title: str = Field(..., description="Job position title")
    department: str = Field(..., description="Department hosting this role")

    # Live DB IDs
    vacancy_id: int | None = Field(None, description="Live MSSQL VacancyRequestID")
    job_profile_id: int | None = Field(None, description="Live MSSQL JobProfileID")
    company_id: int | None = Field(None, description="Live MSSQL CompID")
    department_id: int | None = Field(None, description="Live MSSQL DeptID")
    department_name: str | None = Field(None, description="Live MSSQL DeptName")
    location_id: int | None = Field(None, description="Live MSSQL LocID")

    score: float = Field(
        ..., description="Calculated suitability match score (0.0 - 100.0)"
    )
    overall_score: float = Field(
        default=0.0, description="Deterministic two-stage overall score (0.0 - 100.0)"
    )
    role_score: float = Field(default=0.0, description="Score based on job title and domain match")
    skills_score: float = Field(default=0.0, description="Score based on mandatory/preferred skills")
    experience_score: float = Field(default=0.0, description="Score based on experience match")
    education_score: float = Field(default=0.0, description="Score based on education requirements")
    domain_score: float = Field(default=0.0, description="Score based on industry/domain alignment")
    technology_score: float = Field(default=0.0, description="Score based on technology matches")
    certification_score: float = Field(default=0.0, description="Score based on required certifications")
    responsibilities_score: float = Field(default=0.0, description="Score based on matched responsibilities/keywords")
    coverage: float = Field(default=1.0, description="Percentage of evaluation dimensions actually defined in the vacancy config")
    ranking_reason: str = Field(default="", description="Reason this vacancy was ranked at its position")
    classification: str = Field(
        ..., description="Classification category: HIGH, MEDIUM, or LOW"
    )
    recommendation: str = Field(
        ..., description="Actionable recommendation status for HR/Recruiters"
    )
    matched_skills: list[str] = Field(
        default_factory=list,
        description="Skills present in CV that match job requirements",
    )
    missing_skills: list[str] = Field(
        default_factory=list, description="Required job skills missing from CV"
    )
    matched_keywords: list[str] = Field(
        default_factory=list, description="Preferred keywords found in CV"
    )
    missing_keywords: list[str] = Field(
        default_factory=list, description="Preferred keywords missing from CV"
    )

    # Structured Two-Stage Evaluation Fields
    mandatory_requirements: list[RequirementEvaluation] = Field(
        default_factory=list, description="Evaluated mandatory requirements"
    )
    preferred_requirements: list[RequirementEvaluation] = Field(
        default_factory=list, description="Evaluated preferred requirements"
    )
    optional_requirements: list[RequirementEvaluation] = Field(
        default_factory=list, description="Evaluated optional requirements"
    )
    matched_criteria: list[str] = Field(
        default_factory=list, description="All matched requirement criteria descriptions"
    )
    missing_criteria: list[str] = Field(
        default_factory=list, description="All missing or failed requirement criteria descriptions"
    )
    evidence: dict[str, DualEvidence] = Field(
        default_factory=dict, description="Map of requirement_id to dual CV & Vacancy evidence"
    )
    mandatory_failures: list[MandatoryFailureDetails] = Field(
        default_factory=list, description="Explicit mandatory requirements that failed or partially failed"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Overall confidence level in extraction and evidence completeness"
    )
    hr_review_required: bool = Field(
        default=False, description="Flag indicating mandatory HR review required due to mandatory failure or low score"
    )
    reason: str = Field(
        default="", description="Detailed summary explaining match score, failures, and HR review rationale"
    )
    career_transition_detected: bool = Field(
        default=False, description="Whether a dynamic career transition was detected"
    )
    career_transition_note: str | None = Field(
        default=None, description="Notes on detected career transition"
    )


class CandidateMatchAnalysis(BaseModel):
    primary_department: str = Field(
        ..., description="Top recommended department for candidate"
    )
    best_match: JobMatchResult = Field(..., description="Top matching job opening")
    suitable_openings: list[JobMatchResult] = Field(
        ..., description="All evaluated job openings ranked by match score"
    )
    rejection_policy_note: str = Field(
        default="Candidates are NEVER automatically rejected based on LOW match scores. HR review is always recommended.",
        description="Policy enforcement note regarding LOW score candidate retention",
    )

