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


@pytest.mark.parametrize("stored_name", ["applications", None])
def test_candidate_search_revalidates_stale_or_missing_candidate_names(monkeypatch, stored_name):
    result = {
        "id": "cv_generic_name_refresh",
        "filename": "generic.pdf",
        "status": "COMPLETED",
        "progress": 100,
        "markdown": "## CONTACT\nJordan Lee\napplications@sample.org\n+1 202 555 0187\nAustin, Texas",
        "full_name": stored_name,
        "candidate_name": stored_name,
        "name_confidence": 0.3 if stored_name else 0.0,
        "name_extraction_source": "email_username_fallback" if stored_name else "default",
        "resume_json": {
            "contact_info": {
                "name": stored_name,
                "email": "applications@sample.org",
                "phone": "+1 202 555 0187",
                "location": "Austin, Texas",
                "name_confidence": 0.3 if stored_name else 0.0,
                "extraction_source": "email_username_fallback" if stored_name else "default",
            }
        },
    }
    monkeypatch.setattr(ResultRepository, "list_all_results", lambda: [result])

    response = CandidateSearchService.search_candidates(CandidateSearchRequest())

    assert len(response.candidates) == 1
    assert response.candidates[0].full_name == "Jordan Lee"


def test_candidate_search_revalidates_name_embedded_in_personal_details(monkeypatch):
    result = {
        "id": "cv_generic_inline_name",
        "filename": "generic.pdf",
        "status": "COMPLETED",
        "progress": 100,
        "markdown": (
            "PERSONAL DETAILS NAME : Mr. VIRAL D. HIRANI PERMANENT ADDRESS : 505 Example Road "
            "CONTACT NO : 9913042301 EMAIL : viralhirani1985@gmail.com\n\nEDUCATION QUALIFICATION: -"
        ),
        "full_name": "EDUCATION QUALIFICATION: -",
        "candidate_name": "EDUCATION QUALIFICATION: -",
        "name_confidence": 0.85,
        "name_extraction_source": "header_contact_section",
        "resume_json": {
            "contact_info": {
                "name": "EDUCATION QUALIFICATION: -",
                "email": "viralhirani1985@gmail.com",
                "phone": "9913042301",
                "name_confidence": 0.85,
                "extraction_source": "header_contact_section",
            }
        },
    }
    monkeypatch.setattr(ResultRepository, "list_all_results", lambda: [result])

    response = CandidateSearchService.search_candidates(CandidateSearchRequest())

    assert len(response.candidates) == 1
    assert response.candidates[0].full_name == "VIRAL D. HIRANI"


def test_candidate_search_preserves_canonical_fit_breakdown(monkeypatch):
    score_breakdown = {
        "hierarchy_score": 80.0,
        "designation_role_score": 90.0,
        "skills_score": 85.0,
        "experience_score": 75.0,
        "semantic_similarity_score": 70.0,
        "overall_fit_score": 81.25,
        "hierarchy_mismatch_penalty": 0.0,
        "is_hierarchy_valid": True,
        "match_status": "MATCHED",
    }
    result = {
        "id": "cv_fit_breakdown",
        "filename": "fit_breakdown.pdf",
        "status": "COMPLETED",
        "progress": 100,
        "full_name": "Canonical Candidate",
        "match_analysis": {
            "best_match": {
                "job_title": "Engineer",
                "vacancy_fit_score": 81.25,
                "vacancy_match_status": "MATCHED",
                "score_breakdown": score_breakdown,
                "reason": "Canonical fit evaluated from configured dimensions.",
            }
        },
    }
    monkeypatch.setattr(ResultRepository, "list_all_results", lambda: [result])

    response = CandidateSearchService.search_candidates(CandidateSearchRequest())

    assert len(response.candidates) == 1
    best_match = response.candidates[0].best_match
    assert best_match is not None
    assert best_match["score_breakdown"] == score_breakdown
    assert best_match["vacancy_match_status"] == "MATCHED"


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
