from __future__ import annotations

from app.schemas.contracts import AccessTier, ErrorCode, ErrorResponse
from app.schemas.match import (
    CandidateMatchAnalysis,
    DualEvidence,
    HiringRisk,
    JobMatchResult,
    MandatoryFailureDetails,
    RequirementEvaluation,
    RequirementStatus,
    RequirementTier,
    RiskSeverity,
)
from app.schemas.scoring_config import DEFAULT_COMPONENT_WEIGHTS, ScoringConfig


def test_requirement_evaluation_schema() -> None:
    eval_item = RequirementEvaluation(
        requirement_id="req_python",
        description="Minimum 3 years Python development",
        tier=RequirementTier.MANDATORY,
        status=RequirementStatus.SATISFIED,
        evidence=DualEvidence(
            cv_evidence="6+ years building microservices with Python and FastAPI",
            vacancy_evidence="Required: Python 3+",
            confidence_score=0.95,
        ),
    )
    assert eval_item.requirement_id == "req_python"
    assert eval_item.tier == RequirementTier.MANDATORY
    assert eval_item.status == RequirementStatus.SATISFIED
    assert eval_item.evidence.confidence_score == 0.95


def test_mandatory_failure_details_hydration() -> None:
    legacy_data = {
        "requirement_id": "req_skill_docker",
        "description": "Docker containerization required",
        "reason": "Candidate has no Docker experience listed",
        "score_impact": 20.0,
    }
    failure = MandatoryFailureDetails.model_validate(legacy_data)
    assert failure.failure_code == "MISSING_MANDATORY_SKILL"
    assert failure.score_impact == 20.0


def test_job_match_result_and_candidate_match_analysis() -> None:
    opening = JobMatchResult(
        job_id="job-101",
        job_title="Senior Python Developer",
        department="Engineering",
        vacancy_id=101,
        score=88.5,
        classification="HIGH",
        recommendation="Strong candidate — proceed to interview.",
        mandatory_failures=[],
        hiring_risks=[
            HiringRisk(
                risk_code="COMMUTE_DISTANCE",
                category="Logistics",
                severity=RiskSeverity.LOW,
                title="Commute Distance",
                explanation="Candidate is located outside the primary office zone",
                source="DynamicGeoService",
            )
        ],
    )
    assert opening.vacancy_id == 101
    assert opening.score == 88.5
    assert len(opening.hiring_risks) == 1

    analysis = CandidateMatchAnalysis(
        candidate_name="Alex Mercer",
        suitable_openings=[opening],
        best_match=opening,
    )
    assert analysis.candidate_name == "Alex Mercer"
    assert analysis.best_match is not None
    assert analysis.best_match.vacancy_id == 101


def test_scoring_config() -> None:
    config = ScoringConfig(
        component_weights=dict(DEFAULT_COMPONENT_WEIGHTS),
        match_high_threshold=80.0,
        match_medium_threshold=50.0,
    )
    assert config.match_high_threshold == 80.0
    assert config.component_weights["skills"] == 0.20


def test_error_response_contract() -> None:
    from app.schemas.contracts import CanonicalError

    err = ErrorResponse(
        error=CanonicalError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Request payload failed validation schema",
            correlation_id="corr-12345",
            retryable=False,
        )
    )
    assert err.error.code == ErrorCode.VALIDATION_ERROR
    assert err.error.retryable is False
