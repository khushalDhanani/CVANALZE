import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import app
from app.schemas.work_experience_extraction import WorkExperienceExtractionResponse

client = TestClient(app)

@patch("app.api.experience_extraction.WorkExperienceExtractionEngine.process", new_callable=AsyncMock)
def test_extract_experience_api_success(mock_process):
    # Mocking the response to avoid actual LLM calls
    mock_process.return_value = WorkExperienceExtractionResponse(
        candidate_id="C123",
        reference_date="2026-08-05",
        extraction_status="success",
        detected_date_pattern="DD/MM/YYYY",
        current_employment={
            "is_currently_employed": False,
            "current_job_count": 0,
            "current_employers": []
        },
        experience_summary={
            "gross_experience_days": 100,
            "unique_experience_days": 100,
            "full_time_experience_days": 100,
            "part_time_experience_days": 0,
            "contract_experience_days": 0,
            "temporary_experience_days": 0,
            "apprenticeship_experience_days": 0,
            "internship_experience_days": 0,
            "freelance_experience_days": 0,
            "self_employed_experience_days": 0,
            "completed_years": 0,
            "remaining_months": 3,
            "remaining_days": 0,
            "experience_display": "0 years 3 months",
            "merged_intervals": []
        },
        employment_records=[],
        duplicate_records=[],
        unresolved_employment_text=[],
        global_warnings=[],
        review_reasons=[],
        overall_confidence=0.9,
        requires_human_review=False,
        metadata={
            "prompt_version": "1.0.0",
            "calculation_version": "1.0.0",
            "llm_model": "test-model",
            "cache_hit": False,
            "processing_time_ms": 100
        }
    )

    response = client.post(
        "/api/v1/cv/extract-experience",
        json={
            "candidate_id": "C123",
            "ocr_text": "Sample text",
            "reference_date": "2026-08-05",
            "config": {}
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["candidate_id"] == "C123"
    assert data["extraction_status"] == "success"

def test_extract_experience_api_validation_error():
    response = client.post(
        "/api/v1/cv/extract-experience",
        json={
            # missing required fields
            "ocr_text": "Sample text",
        }
    )
    
    assert response.status_code == 422
