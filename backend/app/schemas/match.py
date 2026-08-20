from __future__ import annotations
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schemas.analysis_versions import AnalysisVersions


class RequirementTier(str, Enum):
    MANDATORY = "MANDATORY"
    PREFERRED = "PREFERRED"
    OPTIONAL = "OPTIONAL"


class RequirementStatus(str, Enum):
    SATISFIED = "SATISFIED"
    PARTIALLY_SATISFIED = "PARTIALLY_SATISFIED"
    FAILED = "FAILED"
    UNVERIFIED = "UNVERIFIED"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


class DualEvidence(BaseModel):
    cv_evidence: str = Field(..., description="Extract/quote or verified fact from candidate CV. When absent or unverified, is 'NO_VERIFIED_EVIDENCE_FOUND'")
    vacancy_evidence: str = Field(..., description="Target requirement description or text from vacancy")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: str = Field(default="VERIFIED_CV", description="Evidence provenance: VERIFIED_CV, GROUNDED_LLM, INFERRED_LLM, VERIFIED_TIMELINE, or NO_EVIDENCE")
    source_section: str | None = Field(default=None, description="Section from which candidate evidence was extracted (e.g. skills, employment, education)")


class RequirementEvaluation(BaseModel):
    requirement_id: str = Field(..., description="Unique identifier for requirement item")
    description: str = Field(..., description="Text description of requirement")
    tier: RequirementTier = Field(..., description="Requirement classification tier")
    status: RequirementStatus = Field(..., description="Evaluation status of requirement")
    evidence: DualEvidence = Field(..., description="Supporting evidence from CV and Vacancy")
    failure_reason: str | None = Field(
        None,
        description="Detailed explanation if requirement failed or partially satisfied",
    )


class RequirementAssessment(BaseModel):
    requirement_id: str = Field(..., description="Unique requirement identifier")
    requirement_type: str = Field(..., description="Requirement domain type (skill, certification, education, experience)")
    status: str = Field(..., description="Evaluation status: SATISFIED, FAILED, or NOT_ASSESSABLE")
    matched_evidence: list[DualEvidence] = Field(default_factory=list, description="Verified matched evidence items")
    missing_evidence: list[str] = Field(default_factory=list, description="Missing requirement elements")
    conclusion: str = Field(..., description="Deterministic requirement evaluation conclusion")
    policy_version: str | None = Field(default=None, description="Resolved policy digest or rule version")


class MandatoryFailureDetails(BaseModel):
    failure_code: str = Field(..., description="Stable machine-readable failure code (e.g. MIN_EXPERIENCE_FAILED)")
    requirement_id: str = Field(..., description="Identifier of failed mandatory requirement")
    description: str = Field(..., description="Requirement description")
    reason: str = Field(..., description="Explicit reason why mandatory requirement was not satisfied")
    score_impact: float = Field(default=0.0, description="Deduction or penalty applied to final score")

    @model_validator(mode="before")
    @classmethod
    def hydrate_legacy_failure_code(cls, value: Any) -> Any:
        """Restore stable identities on failures persisted before failure_code was introduced."""
        if not isinstance(value, dict) or str(value.get("failure_code") or "").strip():
            return value

        hydrated = dict(value)
        requirement_id = str(hydrated.get("requirement_id") or "").strip().lower()
        reason = str(hydrated.get("reason") or "").strip().lower()
        if requirement_id.startswith("req_skill_"):
            failure_code = "MISSING_MANDATORY_SKILL"
        elif requirement_id in {"req_min_experience", "req_exp"}:
            failure_code = "EXPERIENCE_UNKNOWN" if "unknown" in reason or "unparseable" in reason else "MIN_EXPERIENCE_FAILED"
        elif requirement_id == "req_certification":
            failure_code = "MISSING_CERTIFICATION"
        elif requirement_id == "req_max_ctc":
            failure_code = "CTC_MISMATCH"
        elif requirement_id == "req_domain_mismatch":
            failure_code = "DOMAIN_MISMATCH"
        else:
            failure_code = "LEGACY_MANDATORY_FAILURE"
        hydrated["failure_code"] = failure_code
        return hydrated


class VacancyFitScoreBreakdown(BaseModel):
    """Detailed score breakdown for structured hierarchy + semantic vacancy fit evaluation."""
    hierarchy_score: float = Field(default=0.0, description="Hierarchy ID match score (MainDeptID, DeptID, DesigID) (0-100)")
    designation_role_score: float = Field(default=0.0, description="Designation and role alignment score (0-100)")
    skills_score: float = Field(default=0.0, description="Mandatory & preferred skills match score (0-100)")
    experience_score: float = Field(default=0.0, description="Experience & seniority match score (0-100)")
    education_score: float = Field(default=0.0, description="Required education alignment score (0-100)")
    semantic_similarity_score: float = Field(default=0.0, description="Dense vector nomic-embed-text similarity score (0-100)")
    overall_fit_score: float = Field(default=0.0, description="Final weighted vacancy fit score (0-100)")
    hierarchy_mismatch_penalty: float = Field(default=0.0, description="Penalty deduction applied for hierarchy mismatch")
    is_hierarchy_valid: bool | None = Field(default=True, description="Whether MSSQL parent-child hierarchy validation passed; null when validation was unavailable")
    match_status: str = Field(default="MATCHED", description="MATCHED, POTENTIAL_MATCH, or NO_STRONG_VACANCY_MATCH")
    scoring_policy_version: str | None = Field(default=None, description="Active scoring policy version used for breakdown")
    component_assessability: dict[str, str] = Field(default_factory=dict, description="Assessability state per component (VERIFIED, INFERRED, NOT_ASSESSABLE)")


from enum import Enum

class RiskSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"

class HiringRisk(BaseModel):
    risk_code: str = Field(..., description="Deterministic risk code")
    category: str = Field(..., description="General category of the risk")
    severity: RiskSeverity = Field(..., description="Severity level mapped from policy")
    title: str = Field(..., description="Short recruiter-facing title of the risk")
    explanation: str = Field(..., description="Readable explanation generated by Gemma or deterministic fallback")
    evidence: list[str] = Field(default_factory=list, description="Raw structural evidence supporting this risk")
    source: str = Field(..., description="System component that identified the risk")
    requires_manual_review: bool = Field(default=False, description="Whether this risk triggers manual review")


class RiskEvidenceEvent(BaseModel):
    failure_code: str = Field(..., description="Stable deterministic failure identity")
    requirement_id: str | None = Field(default=None, description="Structured requirement identifier")
    evidence: list[str] = Field(default_factory=list, description="Deterministic evidence safe for recruiter display")
    source: str = Field(..., description="System component that emitted the failure")
    integrity_domain: str | None = Field(default=None, description="Deferred integrity domain, when applicable")

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

    score: float = Field(..., description="Calculated suitability match score (0.0 - 100.0)")
    overall_score: float = Field(default=0.0, description="Deterministic two-stage overall score (0.0 - 100.0)")
    vacancy_fit_score: float = Field(default=0.0, description="Final weighted vacancy fit score (0.0 - 100.0)")
    score_breakdown: VacancyFitScoreBreakdown | None = Field(default=None, description="Structured score breakdown across hierarchy, skills, experience, role, and semantic fit")
    vacancy_match_status: str = Field(default="MATCHED", description="MATCHED or NO_STRONG_VACANCY_MATCH")
    role_score: float = Field(default=0.0, description="Score based on job title and domain match")
    skills_score: float = Field(default=0.0, description="Score based on mandatory/preferred skills")
    experience_score: float = Field(default=0.0, description="Score based on experience match")
    education_score: float = Field(default=0.0, description="Score based on education requirements")
    domain_score: float = Field(default=0.0, description="Score based on industry/domain alignment")
    technology_score: float = Field(default=0.0, description="Score based on technology matches")
    certification_score: float = Field(default=0.0, description="Score based on required certifications")
    responsibilities_score: float = Field(default=0.0, description="Score based on matched responsibilities/keywords")
    coverage: float = Field(
        default=1.0,
        description="Percentage of evaluation dimensions actually defined in the vacancy config",
    )
    ranking_reason: str = Field(default="", description="Reason this vacancy was ranked at its position")
    classification: str = Field(..., description="Classification category: HIGH, MEDIUM, or LOW")
    recommendation: str = Field(..., description="Actionable recommendation status for HR/Recruiters")
    matched_skills: list[str] = Field(
        default_factory=list,
        description="Skills present in CV that match job requirements",
    )
    missing_skills: list[str] = Field(default_factory=list, description="Required job skills missing from CV")
    matched_keywords: list[str] = Field(default_factory=list, description="Preferred keywords found in CV")
    missing_keywords: list[str] = Field(default_factory=list, description="Preferred keywords missing from CV")

    # Structured Two-Stage Evaluation Fields
    mandatory_requirements: list[RequirementEvaluation] = Field(default_factory=list, description="Evaluated mandatory requirements")
    preferred_requirements: list[RequirementEvaluation] = Field(default_factory=list, description="Evaluated preferred requirements")
    optional_requirements: list[RequirementEvaluation] = Field(default_factory=list, description="Evaluated optional requirements")
    matched_criteria: list[str] = Field(
        default_factory=list,
        description="All matched requirement criteria descriptions",
    )
    missing_criteria: list[str] = Field(
        default_factory=list,
        description="All missing or failed requirement criteria descriptions",
    )
    evidence: dict[str, DualEvidence] = Field(
        default_factory=dict,
        description="Map of requirement_id to dual CV & Vacancy evidence",
    )
    mandatory_failures: list[MandatoryFailureDetails] = Field(
        default_factory=list,
        description="Explicit mandatory requirements that failed or partially failed",
    )
    mandatory_fails: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Explicit mandatory requirement failure summary list",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence level in extraction and evidence completeness",
    )
    hr_review_required: bool = Field(
        default=False,
        description="Flag indicating mandatory HR review required due to mandatory failure or low score",
    )
    reason: str = Field(
        default="",
        description="Detailed summary explaining match score, failures, and HR review rationale",
    )
    career_transition_detected: bool = Field(default=False, description="Whether a dynamic career transition was detected")
    career_transition_note: str | None = Field(default=None, description="Notes on detected career transition")
    domain_mismatch_capped: bool = Field(
        default=False,
        description="Flag indicating cross-domain guard fired and capped the suitability match score",
    )
    domain_mismatch_reason: str | None = Field(
        default=None,
        description="Explicit explainability reason explaining why cross-domain guard capped the match score",
    )
    retrieval_source: str | None = Field(
        default="keyword",
        description="Retrieval path that selected this vacancy: 'both', 'vector', or 'keyword'",
    )
    candidate_job_family: str | None = Field(default=None, description="Classified job family of the candidate")
    vacancy_job_family: str | None = Field(default=None, description="Classified job family of the target vacancy")
    hiring_risks: list[HiringRisk] = Field(default_factory=list, description="Generated hiring risks and concerns")
    policy_snapshot_id: str | None = Field(default=None, description="Identifier of PolicySnapshot resolved at evaluation start")
    policy_digest: str | None = Field(default=None, description="SHA-256 fingerprint digest of active PolicySnapshot")
    scoring_policy_version: str | None = Field(default=None, description="Active scoring policy version used for calculation")
    component_assessability: dict[str, str] = Field(default_factory=dict, description="Assessability state per component (VERIFIED, INFERRED, NOT_ASSESSABLE)")
    analysis_versions: AnalysisVersions | None = Field(default=None, description="Complete analysis version provenance")

    @model_validator(mode="after")
    def synchronize_canonical_score_and_status(self) -> "JobMatchResult":
        """Keep one final score/status across persistence, APIs, and frontend consumers."""
        canonical_score = self.vacancy_fit_score
        if canonical_score == 0.0 and self.score_breakdown is None:
            canonical_score = self.overall_score if self.overall_score != 0.0 else self.score
        canonical_score = round(max(0.0, min(100.0, float(canonical_score))), 1)
        self.vacancy_fit_score = canonical_score
        self.overall_score = canonical_score
        self.score = canonical_score
        if self.mandatory_failures and self.vacancy_match_status == "MATCHED":
            self.vacancy_match_status = "NO_STRONG_VACANCY_MATCH"
        return self


class CandidateMatchAnalysis(BaseModel):
    full_name: str | None = Field(default=None, description="Extracted candidate full name")
    candidate_name: str | None = Field(default=None, description="Extracted candidate name")
    primary_department: str | None = Field(default=None, description="Top recommended department for candidate")
    best_match: JobMatchResult | None = Field(default=None, description="Top matching job opening")
    suitable_openings: list[JobMatchResult] = Field(..., description="Verified HIGH job matches with no hard disqualifiers, ranked by match score")
    unsuitable_openings: list[JobMatchResult] = Field(
        default_factory=list,
        description="Potential or unsuitable openings retained for HR manual review but not selected as suitable matches",
    )
    rejection_policy_note: str = Field(
        default="Candidates are NEVER automatically rejected based on LOW match scores. HR review is always recommended.",
        description="Policy enforcement note regarding LOW score candidate retention",
    )
    policy_snapshot_id: str | None = Field(default=None, description="Identifier of PolicySnapshot resolved at analysis start")
    policy_digest: str | None = Field(default=None, description="SHA-256 fingerprint digest of active PolicySnapshot")
    scoring_policy_version: str | None = Field(default=None, description="Active scoring policy version used for calculation")
    component_assessability: dict[str, str] = Field(default_factory=dict, description="Assessability state per component (VERIFIED, INFERRED, NOT_ASSESSABLE)")
    analysis_versions: AnalysisVersions | None = Field(default=None, description="Complete analysis version provenance")


JobMatchResult.model_rebuild()
CandidateMatchAnalysis.model_rebuild()
