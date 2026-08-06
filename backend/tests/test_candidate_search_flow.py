import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.repositories.result import ResultRepository
from app.services.candidate_search_service import CandidateSearchService
from app.schemas.candidate_search import CandidateSearchRequest

client = TestClient(app)


def test_candidate_search_excludes_processing_records_by_default(tmp_path, monkeypatch):
    """Verify that candidate search excludes incomplete processing records from directory view."""
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "RESULTS_DIR", tmp_path / "results")

    # 1. Interim processing marker
    interim_data = {
        "id": "cv_document_processing_test",
        "scan_id": "cv_document_processing_test",
        "status": "processing",
        "progress": 30,
        "stage": "parsing",
        "filename": "processing_test.pdf",
    }
    ResultRepository.atomic_save_result("cv_document_processing_test.json", interim_data)

    # 2. Complete candidate record
    complete_data = {
        "id": "cv_document_complete_test",
        "scan_id": "cv_document_complete_test",
        "status": "COMPLETED",
        "progress": 100,
        "stage": "complete",
        "is_complete": True,
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "job_title": "Senior Cloud Engineer",
        "company_name": "Tech Corp",
        "location": "San Francisco, CA",
        "match_analysis": {
            "primary_department": "Engineering",
        },
    }
    ResultRepository.atomic_save_result("cv_document_complete_test.json", complete_data)

    # Query candidate search
    res = CandidateSearchService.search_candidates(CandidateSearchRequest())
    candidate_ids = [c.id for c in res.candidates]

    assert "cv_document_complete_test" in candidate_ids
    assert "cv_document_processing_test" not in candidate_ids


def test_get_status_returns_processing_while_incomplete(tmp_path, monkeypatch):
    """Verify GET /api/match/status returns processing response while progress < 100."""
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "RESULTS_DIR", tmp_path / "results")

    cv_key = "cv_document_status_test"
    interim_data = {
        "id": cv_key,
        "scan_id": cv_key,
        "status": "processing",
        "progress": 45,
        "stage": "extraction",
        "match_analysis": {
            "scan_id": cv_key,
        },
    }
    ResultRepository.atomic_save_result(f"{cv_key}.json", interim_data)

    res = client.get(f"/api/match/status/{cv_key}")
    assert res.status_code == 200
    res_json = res.json()
    assert res_json.get("status") == "processing"
    assert res_json.get("progress") == 45
