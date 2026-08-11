import pytest
from unittest.mock import patch
import fitz
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.repositories.processing_job import ProcessingJobRepository
from app.repositories.result import ResultRepository
from app.schemas.contracts import JobState, ProcessingExecutionMode, ProcessingJobRecord
from app.services.processing_queue import ProcessingQueueService

client = TestClient(app)


def test_start_worker_queue_configuration():
    """Verify the CV worker listens only to the configured FIFO CV queue."""
    from start_worker import main
    with patch("start_worker.RuntimeDependencyWorker") as mock_worker:
        with patch("start_worker.Redis"), patch("start_worker.settings.RQ_WORKER_MAX_JOBS", 0), \
             patch("start_worker.settings.CV_PROCESSING_CONCURRENCY", 1), \
             patch("start_worker.wait_for_cv_runtime_dependencies") as wait_for_config, \
             patch("start_worker.start_config_invalidation_listener") as start_listener:
            mock_worker.return_value.work.return_value = None
            main()
            wait_for_config.assert_called_once_with(process_name="CV_WORKER")
            start_listener.assert_called_once_with()
            assert mock_worker.called
            queues = mock_worker.call_args[0][0]
            queue_names = [q.name for q in queues]
            assert queue_names == [settings.RQ_QUEUE_NAME]
            assert mock_worker.call_args.kwargs["maintenance_interval"] == settings.RQ_MAINTENANCE_INTERVAL_SECONDS
            mock_worker.return_value.work.assert_called_once_with(with_scheduler=True)


def test_status_resolution_by_cv_id_alias(tmp_path, monkeypatch):
    """Verify that GET /api/match/status/{cv_id} resolves cv_document_{cv_id} canonical keys."""
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "RESULTS_DIR", tmp_path / "results")

    cv_id = "cv_ut1765894215"
    canonical_key = f"cv_document_{cv_id}"

    # 1. Create job record under canonical_key with cv_id alias
    job_record = ProcessingJobRecord(
        job_id="job_test_123",
        cv_key=canonical_key,
        cv_id=cv_id,
        content_hash="dummy_hash",
        filename="test_cv.pdf",
        storage_filename="test_cv.pdf",
        parser_version="1.0.0",
        schema_version="2.0.0",
        state=JobState.QUEUED,
        progress=10,
        stage="queued",
        execution_mode=ProcessingExecutionMode.RQ,
    )
    ProcessingJobRepository.save(job_record)

    # 2. Verify get_by_cv_key resolves for raw cv_id
    retrieved_job = ProcessingJobRepository.get_by_cv_key(cv_id)
    assert retrieved_job is not None
    assert retrieved_job.cv_key == canonical_key

    # 3. Save completed result under canonical_key
    result_data = {
        "id": canonical_key,
        "scan_id": canonical_key,
        "cv_id": cv_id,
        "status": "COMPLETED",
        "progress": 100,
        "stage": "complete",
        "is_complete": True,
        "message": "100% - CV parsing & job matching complete!",
        "match_analysis": {
            "match_status": "NO_SUITABLE_MATCH",
            "has_genuine_match": False,
            "active_vacancy_summary": "No active match",
        },
    }
    ResultRepository.atomic_save_result(f"{canonical_key}.json", result_data)

    # 4. Verify ResultRepository.resolve_result resolves for raw cv_id
    resolved = ResultRepository.resolve_result(cv_id)
    assert resolved is not None
    assert resolved.get("id") == canonical_key

    # 5. Query status API endpoint for raw cv_id
    res = client.get(f"/api/match/status/{cv_id}")
    assert res.status_code == 200
    res_json = res.json()
    assert res_json.get("match_status") == "NO_SUITABLE_MATCH" or res_json.get("status") == "COMPLETED"
