from __future__ import annotations
import pytest
from app.repositories.result import ResultRepository
from app.schemas.candidate_search import CandidateSearchRequest
from app.services.candidate_search_service import CandidateSearchService


def test_is_completed_result_validation():
    completed_record = {
        "status": "COMPLETED",
        "is_complete": True,
        "progress": 100,
        "persistence_status": "durable",
    }
    assert ResultRepository.is_completed_result(completed_record) is True

    processing_record = {
        "status": "PROCESSING",
        "is_complete": False,
        "progress": 35,
        "persistence_status": "interim",
    }
    assert ResultRepository.is_completed_result(processing_record) is False

    failed_record = {
        "status": "FAILED",
        "is_complete": False,
        "progress": 50,
    }
    assert ResultRepository.is_completed_result(failed_record) is False


def test_list_all_results_filtering():
    items = ResultRepository.list_all_results(include_incomplete=False)
    for item in items:
        assert ResultRepository.is_completed_result(item) is True

    all_items = ResultRepository.list_all_results(include_incomplete=True)
    assert len(all_items) >= len(items)


def test_candidate_search_service_completion_filter():
    req_default = CandidateSearchRequest(include_incomplete=False, limit=50)
    res_default = CandidateSearchService.search_candidates(req_default)
    for cand in res_default.candidates:
        assert cand.is_complete is True

    req_all = CandidateSearchRequest(include_incomplete=True, limit=50)
    res_all = CandidateSearchService.search_candidates(req_all)
    assert res_all.total_found >= res_default.total_found
