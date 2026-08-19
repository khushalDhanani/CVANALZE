from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.job_context import JobEvaluationContext
from app.schemas.match import MandatoryFailureDetails
from app.services.match_evaluators import ScoringConfig, VacancyFitEvaluator


def test_canonical_score_and_status_no_recalculation():
    opening = {
        "vacancy_match_status": "POTENTIAL_MATCH",
        "vacancy_fit_score": 60.0
    }
    # Should not recalculate NO_STRONG_MATCH just because 60 < high_threshold
    status = VacancyFitEvaluator.classify_opening_fit(opening, high_threshold=80.0, potential_threshold=50.0)
    assert status == "POTENTIAL_MATCH"

    opening_failed = {
        "vacancy_match_status": "NO_STRONG_VACANCY_MATCH",
        "vacancy_fit_score": 89.0, # e.g. some rogue legacy field
        "mandatory_failures": [{"requirement_id": "test"}]
    }
    # Should completely ignore the score and just trust the status
    status = VacancyFitEvaluator.classify_opening_fit(opening_failed, high_threshold=80.0, potential_threshold=50.0)
    assert status == "NO_STRONG_MATCH"

def test_mandatory_failure_caps_llm_boost():
    config = ScoringConfig(match_high_threshold=70.0, match_medium_threshold=50.0)
    # rejection_cap will be 49.9
    
    # Simulate a candidate with 0 raw_fit_score but massive LLM boost of 100.0
    # Mandatory failure should still cap it at 49.9
    
    class MockCompResults:
        role_score = 0
        skills_score = 0
        experience_score = 0
        education_score = 0
        responsibilities_score = 0

    job = JobEvaluationContext.create({})
    context = CandidateAnalysisContext.create(cv_text="")
    
    failures = [MandatoryFailureDetails(requirement_id="test", description="test", reason="test", score_impact=100.0)]
    
    res = VacancyFitEvaluator.evaluate_fit(
        context=context,
        job=job,
        comp_results=MockCompResults(),
        mandatory_failures=failures,
        scoring_config=config,
        llm_boost=100.0
    )
    
    assert res.vacancy_fit_score == 49.9
    assert res.match_status == "NO_STRONG_VACANCY_MATCH"


def test_legacy_contradictory_results_normalized():
    opening_failed = {
        "vacancy_match_status": "NO_STRONG_VACANCY_MATCH",
        "vacancy_fit_score": 89.0, # e.g. some rogue legacy field
        "mandatory_failures": [{"requirement_id": "test"}]
    }
    # Should resolve to 49.9 (medium threshold - 0.1) instead of 89.0
    resolved_score = VacancyFitEvaluator.resolve_opening_score(opening_failed)
    assert resolved_score == 49.9

    # Custom scoring config with different medium threshold and epsilon
    custom_cfg = ScoringConfig(match_medium_threshold=55.0, rejection_score_epsilon=0.5)
    custom_resolved = VacancyFitEvaluator.resolve_opening_score(opening_failed, scoring_config=custom_cfg)
    assert custom_resolved == 54.5
