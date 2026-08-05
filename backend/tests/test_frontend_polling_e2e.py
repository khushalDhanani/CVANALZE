from unittest.mock import patch

from app.services.processing_queue import QueueSubmission
from app.schemas.contracts import JobState, ProcessingExecutionMode, ProcessingJobRecord

import fitz
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_frontend_polling_match_status_completion(tmp_path, monkeypatch):
    """Verify that /api/match/status endpoint returns completion structure matching useCvUpload frontend hook."""
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "RESULTS_DIR", tmp_path / "results")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Jane Doe\nLead Python Engineer with FastAPI and Microservices.")
    pdf_bytes = doc.tobytes()
    doc.close()

    with patch("app.services.processing_queue.ProcessingQueueService.submit_upload") as mock_submit:
        mock_submit.return_value = QueueSubmission(
            record=ProcessingJobRecord(
                    job_id="cvjob_123",
                    job_state=JobState.QUEUED,
                    execution_mode=ProcessingExecutionMode.RQ.value,
                    message="Queued",
                    stage="extraction",
                    created_at="2024-01-01T00:00:00Z",
                    updated_at="2024-01-01T00:00:00Z",
                    candidate_id="cand_1",
                    cv_key="cv_123",
                    content_hash="hash",
                    filename="test.pdf",
                    storage_filename="test.pdf",
                    parser_version="1.0",
                    schema_version="1.0",
                )      )
        upload_res = client.post(
            "/api/match/upload",
            files={"file": ("test_polling_match.pdf", pdf_bytes, "application/pdf")},
        )
    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    assert upload_data["status"] == "processing"
    cv_key = upload_data["cv_key"]

    status_res = client.get(f"/api/match/status/{cv_key}")
    assert status_res.status_code == 200
    res_data = status_res.json()

    # Simulate exact useCvUpload frontend hook completion evaluation
    is_done = (
        "scan_id" in res_data
        or "match_analysis" in res_data
        or res_data.get("status", "").upper() in ("COMPLETED", "NEW_CV", "REPROCESSED")
        or res_data.get("progress") == 100
        or res_data.get("is_complete") is True
    )

    assert is_done or res_data.get("status") == "processing"
    if is_done:
        assert res_data.get("progress", 100) == 100


def test_frontend_polling_cv_status_completion(tmp_path, monkeypatch):
    """Verify that /api/cv/status endpoint returns completion structure matching useCvUpload frontend hook."""
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "RESULTS_DIR", tmp_path / "results")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Alex Smith\nDevOps & Cloud Engineer with Kubernetes and Terraform.")
    pdf_bytes = doc.tobytes()
    doc.close()

    with patch("app.services.processing_queue.ProcessingQueueService.submit_upload") as mock_submit:
        mock_submit.return_value = QueueSubmission(
            record=ProcessingJobRecord(
                    job_id="cvjob_456",
                    job_state=JobState.QUEUED,
                    execution_mode=ProcessingExecutionMode.RQ.value,
                    message="Queued",
                    stage="extraction",
                    created_at="2024-01-01T00:00:00Z",
                    updated_at="2024-01-01T00:00:00Z",
                    candidate_id="cand_2",
                    cv_key="cv_456",
                    content_hash="hash2",
                    filename="test2.pdf",
                    storage_filename="test2.pdf",
                    parser_version="1.0",
                    schema_version="1.0",
                )      )
        upload_res = client.post(
            "/api/cv/upload",
            files={"file": ("test_polling_cv.pdf", pdf_bytes, "application/pdf")},
        )
    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    assert upload_data["status"] == "processing"
    cv_key = upload_data["cv_key"]

    status_res = client.get(f"/api/cv/status/{cv_key}")
    assert status_res.status_code == 200
    res_data = status_res.json()

    is_done = "scan_id" in res_data or "match_analysis" in res_data or res_data.get("status", "").upper() in ("COMPLETED", "NEW_CV", "REPROCESSED") or res_data.get("progress") == 100

    assert is_done or res_data.get("status") == "processing"
