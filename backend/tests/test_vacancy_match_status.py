"""
Comprehensive tests for Vacancy Match Status Refactoring.
Verifies that VacancyFitEvaluator is the canonical match decision source and that RecommendationService
correctly presents all 7 canonical match decision states:
1. MATCHED
2. POTENTIAL_MATCH
3. NO_STRONG_MATCH
4. NO_ACTIVE_VACANCIES
5. ANALYSIS_NOT_AVAILABLE
6. PROCESSING
7. FAILED
"""

from unittest.mock import patch
import pytest

from app.schemas.scoring_config import ScoringConfig
from app.services.match_evaluators import VacancyFitEvaluator, VacancyMatchStatus
from app.services.recommendation_service import RecommendationService


def test_vacancy_fit_evaluator_classify_opening_fit():
    # 1. Strong Match
    matched_op = {
        "vacancy_fit_score": 85.0,
        "classification": "HIGH",
        "vacancy_match_status": "MATCHED",
    }
    assert VacancyFitEvaluator.classify_opening_fit(matched_op, high_threshold=70.0) == "MATCHED"

    # 2. Potential Match (Score between 50 and 70)
    potential_op = {
        "vacancy_fit_score": 62.0,
        "classification": "MEDIUM",
        "vacancy_match_status": "POTENTIAL_MATCH",
    }
    assert VacancyFitEvaluator.classify_opening_fit(potential_op, high_threshold=70.0, potential_threshold=50.0) == "POTENTIAL_MATCH"

    # 3. No Strong Match (Low Score)
    weak_op = {
        "vacancy_fit_score": 42.0,
        "classification": "LOW",
        "vacancy_match_status": "NO_STRONG_VACANCY_MATCH",
    }
    assert VacancyFitEvaluator.classify_opening_fit(weak_op, high_threshold=70.0, potential_threshold=50.0) == "NO_STRONG_MATCH"

    # 4. Domain Rejection Override
    rejected_op = {
        "vacancy_fit_score": 88.0,
        "classification": "HIGH",
        "domain_mismatch_capped": True,
    }
    assert VacancyFitEvaluator.classify_opening_fit(rejected_op, high_threshold=70.0) == "NO_STRONG_MATCH"


def test_determine_candidate_match_status_all_7_states():
    dummy_vacancies = [{"id": 1, "title": "Software Developer"}]

    # State 1: ANALYSIS_NOT_AVAILABLE (Candidate record not found or None)
    status_1 = VacancyFitEvaluator.determine_candidate_match_status(
        candidate_id="unknown_id",
        result_data=None,
        vacancies_evaluated=[],
        has_active_vacancies=True,
    )
    assert status_1 == VacancyMatchStatus.ANALYSIS_NOT_AVAILABLE.value

    # State 2: PROCESSING
    status_2 = VacancyFitEvaluator.determine_candidate_match_status(
        candidate_id="proc_cand",
        result_data={"status": "processing"},
        vacancies_evaluated=[],
        has_active_vacancies=True,
    )
    assert status_2 == VacancyMatchStatus.PROCESSING.value

    # State 3: FAILED
    status_3 = VacancyFitEvaluator.determine_candidate_match_status(
        candidate_id="failed_cand",
        result_data={"status": "failed"},
        vacancies_evaluated=[],
        has_active_vacancies=True,
    )
    assert status_3 == VacancyMatchStatus.FAILED.value

    # State 4: NO_ACTIVE_VACANCIES
    status_4 = VacancyFitEvaluator.determine_candidate_match_status(
        candidate_id="completed_cand",
        result_data={"status": "completed"},
        vacancies_evaluated=[],
        has_active_vacancies=False,
    )
    assert status_4 == VacancyMatchStatus.NO_ACTIVE_VACANCIES.value

    # State 5: MATCHED
    matched_openings = [{
        "vacancy_fit_score": 90.0,
        "classification": "HIGH",
        "vacancy_match_status": "MATCHED",
    }]
    status_5 = VacancyFitEvaluator.determine_candidate_match_status(
        candidate_id="completed_cand",
        result_data={"status": "completed"},
        vacancies_evaluated=matched_openings,
        has_active_vacancies=True,
    )
    assert status_5 == VacancyMatchStatus.MATCHED.value

    # State 6: POTENTIAL_MATCH
    potential_openings = [{
        "vacancy_fit_score": 60.0,
        "classification": "MEDIUM",
        "vacancy_match_status": "POTENTIAL_MATCH",
    }]
    status_6 = VacancyFitEvaluator.determine_candidate_match_status(
        candidate_id="completed_cand",
        result_data={"status": "completed"},
        vacancies_evaluated=potential_openings,
        has_active_vacancies=True,
    )
    assert status_6 == VacancyMatchStatus.POTENTIAL_MATCH.value

    # State 7: NO_STRONG_MATCH (Analysis succeeded, active vacancies evaluated, but none passed fit)
    weak_openings = [{
        "vacancy_fit_score": 35.0,
        "classification": "LOW",
        "vacancy_match_status": "NO_STRONG_VACANCY_MATCH",
    }]
    status_7 = VacancyFitEvaluator.determine_candidate_match_status(
        candidate_id="completed_cand",
        result_data={"status": "completed"},
        vacancies_evaluated=weak_openings,
        has_active_vacancies=True,
    )
    assert status_7 == VacancyMatchStatus.NO_STRONG_MATCH.value


def test_recommendation_service_consistency_with_evaluator():
    # 1. Missing candidate returns ANALYSIS_NOT_AVAILABLE
    with patch("app.repositories.result.ResultRepository.resolve_result", return_value=None), \
         patch("app.repositories.result.ResultRepository.read_result_by_filename", return_value=None):
        recs = RecommendationService.get_candidate_recommendations("missing_candidate")
        assert recs["hiring_recommendation"] == "ANALYSIS_NOT_AVAILABLE"

    # 2. Candidate in processing returns PROCESSING
    proc_result = {"candidate_id": "proc_1", "status": "processing"}
    with patch("app.repositories.result.ResultRepository.resolve_result", return_value=proc_result):
        recs = RecommendationService.get_candidate_recommendations("proc_1")
        assert recs["hiring_recommendation"] == "PROCESSING"

    # 3. Candidate failed returns FAILED
    failed_result = {"candidate_id": "failed_1", "status": "failed"}
    with patch("app.repositories.result.ResultRepository.resolve_result", return_value=failed_result):
        recs = RecommendationService.get_candidate_recommendations("failed_1")
        assert recs["hiring_recommendation"] == "FAILED"

    # 4. Empty job database returns NO_ACTIVE_VACANCIES
    comp_result = {
        "candidate_id": "comp_1",
        "status": "completed",
        "match_analysis": {"suitable_openings": []},
    }
    with patch("app.repositories.result.ResultRepository.resolve_result", return_value=comp_result), \
         patch("app.repositories.job.JobRepository.get_all_jobs", return_value=[]):
        recs = RecommendationService.get_candidate_recommendations("comp_1")
        assert recs["hiring_recommendation"] == "NO_ACTIVE_VACANCIES"

    # 5. Candidate with evaluated vacancies all low score returns NO_STRONG_MATCH
    weak_match_result = {
        "candidate_id": "comp_weak",
        "status": "completed",
        "match_analysis": {
            "suitable_openings": [{
                "vacancy_id": 99,
                "job_title": "Senior Engineer",
                "department": "Engineering",
                "score": 30.0,
                "classification": "LOW",
                "vacancy_match_status": "NO_STRONG_VACANCY_MATCH",
            }]
        },
    }
    active_jobs = [{"id": 99, "title": "Senior Engineer", "department": "Engineering"}]
    with patch("app.repositories.result.ResultRepository.resolve_result", return_value=weak_match_result), \
         patch("app.repositories.job.JobRepository.get_all_jobs", return_value=active_jobs):
        recs = RecommendationService.get_candidate_recommendations("comp_weak")
        assert recs["hiring_recommendation"] == "NO_STRONG_MATCH"

    # 6. Candidate with strong opening returns MATCHED
    strong_match_result = {
        "candidate_id": "comp_strong",
        "status": "completed",
        "match_analysis": {
            "suitable_openings": [{
                "vacancy_id": 100,
                "job_title": "Lead Architect",
                "department": "Engineering",
                "score": 92.0,
                "classification": "HIGH",
                "vacancy_match_status": "MATCHED",
            }]
        },
    }
    active_jobs_strong = [{"id": 100, "title": "Lead Architect", "department": "Engineering"}]
    with patch("app.repositories.result.ResultRepository.resolve_result", return_value=strong_match_result), \
         patch("app.repositories.job.JobRepository.get_all_jobs", return_value=active_jobs_strong):
        recs = RecommendationService.get_candidate_recommendations("comp_strong")
        assert recs["hiring_recommendation"] == "MATCHED"
        assert len(recs["best_vacancies"]) == 1
