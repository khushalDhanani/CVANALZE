from app.schemas.analysis import EnrichedCandidateAnalysis
from app.schemas.match import MandatoryFailureDetails


def _legacy_failure(requirement_id: str, reason: str = "Legacy failure") -> dict:
    return {
        "requirement_id": requirement_id,
        "description": "Legacy mandatory requirement",
        "reason": reason,
        "score_impact": 20.0,
    }


def _legacy_match(failure: dict) -> dict:
    return {
        "job_id": "1008",
        "job_title": "Assistant Lead (EHS)",
        "department": "EHS Team",
        "score": 37.3,
        "classification": "LOW",
        "recommendation": "Manual HR review required.",
        "mandatory_failures": [failure],
    }


def test_enriched_analysis_hydrates_legacy_minimum_experience_failure_code():
    legacy_failure = _legacy_failure(
        "req_min_experience",
        "Candidate experience (7.5 yrs) is less than required minimum (10.0 yrs).",
    )

    analysis = EnrichedCandidateAnalysis.model_validate(
        {
            "best_match": _legacy_match(legacy_failure),
            "suitable_openings": [],
            "unsuitable_openings": [_legacy_match(legacy_failure)],
        }
    )

    assert analysis.best_match is not None
    assert analysis.best_match.mandatory_failures[0].failure_code == "MIN_EXPERIENCE_FAILED"
    assert analysis.unsuitable_openings[0].mandatory_failures[0].failure_code == "MIN_EXPERIENCE_FAILED"


def test_legacy_failure_hydration_preserves_current_code_and_uses_neutral_fallback():
    current = MandatoryFailureDetails.model_validate(
        {**_legacy_failure("req_min_experience"), "failure_code": "CURRENT_CODE"}
    )
    unknown = MandatoryFailureDetails.model_validate(_legacy_failure("req_custom_requirement"))

    assert current.failure_code == "CURRENT_CODE"
    assert unknown.failure_code == "LEGACY_MANDATORY_FAILURE"


def test_legacy_failure_hydration_matches_current_evaluator_codes():
    expected_codes = {
        "req_skill_work_permit": "MISSING_MANDATORY_SKILL",
        "req_certification": "MISSING_CERTIFICATION",
        "req_max_ctc": "CTC_MISMATCH",
        "req_domain_mismatch": "DOMAIN_MISMATCH",
    }

    for requirement_id, expected_code in expected_codes.items():
        failure = MandatoryFailureDetails.model_validate(_legacy_failure(requirement_id))
        assert failure.failure_code == expected_code

    unknown_experience = MandatoryFailureDetails.model_validate(
        _legacy_failure("req_exp", "Experience is UNKNOWN due to unparseable dates.")
    )
    assert unknown_experience.failure_code == "EXPERIENCE_UNKNOWN"
