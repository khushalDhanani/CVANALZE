from __future__ import annotations
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.classification_types import AISuggestion, MatchStatus, NormalizedClassification
from app.schemas.match import JobMatchResult
from app.schemas.normalized_resume import NormalizedResume


class QwenCVAnalysis(BaseModel):
    skill_matches: list[str] = Field(default_factory=list, description="Direct matches for required skills from CV")
    inferred_skills: list[str] = Field(default_factory=list, description="Skills inferred from CV content or synonyms")
    missing_critical: list[str] = Field(default_factory=list, description="Crucial requirements missing")
    semantic_reason: str = Field(..., description="Explanation of why this candidate fits or lacks fit")


class DynamicMatchedVacancy(BaseModel):
    vacancy_id: int
    semantic_reason: str
    inferred_skills: list[str] = Field(default_factory=list)


class DynamicMappingResponse(BaseModel):
    matched_vacancies: list[DynamicMatchedVacancy] = Field(default_factory=list)


class ClassifiedRequirementItem(BaseModel):
    requirement_id: str = Field(..., description="Unique identifier for requirement item")
    description: str = Field(..., description="Description of requirement")
    tier: str = Field(default="MANDATORY", description="Tier: MANDATORY, PREFERRED, or OPTIONAL")
    status: str = Field(
        default="SATISFIED",
        description="Status: SATISFIED, PARTIALLY_SATISFIED, or FAILED",
    )
    failure_reason: str | None = Field(default=None, description="Explanation if requirement failed")


class RequirementEvidence(BaseModel):
    cv_evidence: str = Field(default="", description="Quote or fact from CV text")
    vacancy_evidence: str = Field(default="", description="Target requirement text from vacancy")


class OptimizedCandidateProfile(BaseModel):
    core_skills: list[str] = Field(default_factory=list)
    inferred_skills: list[str] = Field(default_factory=list)
    relevant_experience_years: float | None = None
    education_domains: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    current_role: str | None = None
    professional_domains: list[str] = Field(default_factory=list)
    recommended_department: str | None = None
    professional_domain: str | None = None
    strengths: list[str] = Field(default_factory=list)
    suitable_job_roles: list[str] = Field(default_factory=list)


class OptimizedVacancyMatch(BaseModel):
    vacancy_id: int | str
    semantic_reason: str = ""
    inferred_skills: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    missing_critical: list[str] = Field(default_factory=list)
    semantic_fit_score: float = Field(default=0.0, ge=0.0, le=100.0)
    classified_requirements: list[ClassifiedRequirementItem] = Field(default_factory=list)
    evidence_snippets: dict[str, RequirementEvidence] = Field(default_factory=dict)
    career_transition_detected: bool = False
    career_transition_note: str | None = None


class OptimizedLLMMatchResponse(BaseModel):
    candidate_profile: OptimizedCandidateProfile = Field(default_factory=OptimizedCandidateProfile)
    matched_vacancies: list[OptimizedVacancyMatch] = Field(default_factory=list)
    active_vacancy_summary: str = Field(default="No suitable active vacancy found.")
    ai_career_summary: str = Field(default="")


class PipelineStageMetrics(BaseModel):
    upload_ms: float = 0.0
    docling_extraction_ms: float = 0.0
    resume_json_ms: float = 0.0
    db_query_ms: float = 0.0
    cache_lookup_ms: float = 0.0
    json_loading_ms: float = 0.0
    vacancy_retrieval_ms: float = 0.0
    prefilter_ms: float = 0.0
    candidate_context_ms: float = 0.0
    vacancy_context_ms: float = 0.0
    evaluator_requirement_ms: float = 0.0
    evaluator_transition_ms: float = 0.0
    evaluator_component_ms: float = 0.0
    evaluator_cross_domain_ms: float = 0.0
    evaluator_recommendation_ms: float = 0.0
    prompt_construction_ms: float = 0.0
    token_count: int = 0
    context_char_count: int = 0
    ollama_request_ms: float = 0.0
    model_inference_ms: float = 0.0
    json_validation_ms: float = 0.0
    scoring_ms: float = 0.0
    matching_ms: float = 0.0
    response_generation_ms: float = 0.0
    total_execution_ms: float = 0.0
    vacancies_before_filtering: int = 0
    vacancies_after_filtering: int = 0
    cache_hit: bool = False
    cache_hits: int = 0
    cache_misses: int = 0
    average_cv_processing_ms: float = 0.0


class EnrichedJobMatchResult(JobMatchResult):
    llm_reason: str = Field(default="", description="Qwen's semantic explanation of the fit")
    inferred_skills: list[str] = Field(default_factory=list, description="Additional skills inferred by Qwen")


class EnrichedCandidateAnalysis(BaseModel):
    status: str | None = Field(default="COMPLETED", description="Status of processing job")
    progress: int | None = Field(default=100, description="Progress percentage")
    stage: str | None = Field(default="complete", description="Current stage")
    is_complete: bool | None = Field(default=True, description="True if completed")
    job_id: str | None = Field(default=None, description="Content-addressed background processing job ID")
    job_state: str | None = Field(default=None, description="Canonical background processing state")
    execution_mode: str | None = Field(default=None, description="Background execution mode")
    retry_count: int | None = Field(default=None, description="Number of processing attempts already started")
    full_name: str | None = Field(default=None, description="Extracted candidate full name")
    candidate_name: str | None = Field(default=None, description="Extracted candidate name")
    primary_department: str | None = Field(default=None, description="Top recommended department for candidate")
    recommended_department: str | None = Field(default=None, description="Recommended department derived from candidate profile")
    professional_domain: str | None = Field(default=None, description="Candidate's specialized professional domain")
    strengths: list[str] = Field(default_factory=list, description="Key strengths identified from CV")
    suitable_job_roles: list[str] = Field(default_factory=list, description="Suitable job roles for candidate")
    has_genuine_match: bool = Field(
        default=False,
        description="True if a genuine match with an active vacancy exists",
    )
    active_vacancy_summary: str = Field(
        default="No suitable active vacancy found.",
        description="Summary of active vacancy match or fallback message",
    )
    scoring_profile_code: str | None = Field(default=None, description="Scoring profile code used for evaluation")
    scoring_profile_version: str | None = Field(default=None, description="Scoring profile version/timestamp used")
    config_version: str | None = Field(default=None, description="Configuration Governance profile version tag")
    prompt_version: str | None = Field(default=None, description="Prompt Template version tag")
    ai_career_summary: str = Field(
        default="",
        description="Independent AI analysis of candidate profile, strengths, department, and suitable roles",
    )
    best_match: EnrichedJobMatchResult | None = Field(default=None, description="Top matching job opening")
    suitable_openings: list[EnrichedJobMatchResult] = Field(..., description="Job openings classified as HIGH or MEDIUM, ranked by match score")
    unsuitable_openings: list[EnrichedJobMatchResult] = Field(
        default_factory=list,
        description="Job openings classified as LOW, retained for HR manual review but not suitable matches",
    )
    rejection_policy_note: str = Field(
        default="Candidates are NEVER automatically rejected based on LOW match scores. HR review is always recommended.",
        description="Policy enforcement note regarding LOW score candidate retention",
    )
    llm_skipped: bool = Field(
        default=False,
        description="True if the LLM call was bypassed due to an unambiguous rule-based match",
    )
    normalized_resume: NormalizedResume | None = Field(
        default=None,
        description="Additive typed resume data with raw/normalized values, confidence, and evidence",
    )
    classification: NormalizedClassification | None = Field(
        default=None,
        description="Structured taxonomy classification with DB identifiers, industry labels, confidence, and evidence",
    )
    ai_career_suggestions: list[AISuggestion] = Field(
        default_factory=list,
        description="AI career suggestions when no DB match found — clearly separated from verified DB matches",
    )
    match_status: MatchStatus = Field(
        default=MatchStatus.NO_SUITABLE_MATCH,
        description="Top level match status indicating if this candidate matches an active vacancy or DB profile",
    )
    freshness_status: str = Field(
        default="FRESH",
        description="Indicates if the candidate data or vacancy data used is stale compared to the DB",
    )
    source_watermark: str | None = Field(
        default=None,
        description="Source system watermark (timestamp or version) when this analysis was synchronized",
    )
    source_snapshot: str | None = Field(
        default=None,
        description="A snapshot of the original source payload for auditing",
    )


class HRReviewRequest(BaseModel):
    scan_id: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="The ID of the scan/analysis result",
    )
    job_id: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="The ID of the job being reviewed against",
    )
    corrected_score: float | None = Field(None, description="HR's corrected score if any")
    corrected_classification: str | None = Field(None, max_length=50, description="HR's corrected classification if any")
    feedback_notes: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_HR_FEEDBACK_LENGTH_CHARS,
        description="HR notes on why the score/classification was changed or approved",
    )


class TrainingExample(BaseModel):
    scan_id: str
    job_id: str
    cv_text: str
    job_requirements: dict[str, Any]
    original_llm_analysis: dict[str, Any]
    original_score: float
    original_classification: str
    hr_corrected_score: float | None
    hr_corrected_classification: str | None
    hr_feedback: str
    timestamp: str
