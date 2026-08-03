import hashlib
from contextlib import nullcontext
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core.cache import MemoryCache, processing_job_cache_manager
from app.core.config import settings
from app.repositories.processing_job import ProcessingJobRepository
from app.repositories.result import ResultRepository
from app.schemas.contracts import JobState, ProcessingExecutionMode
from app.services import processing_queue
from app.services.processing_queue import ProcessingQueueService, process_cv_job
from app.services.upload_service import StoredUpload, UploadService


@pytest.fixture(autouse=True)
def isolate_processing_jobs(monkeypatch):
    monkeypatch.setattr(processing_job_cache_manager, "_providers", [MemoryCache(max_size=100)])
    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "RQ_DEVELOPMENT_FALLBACK_ENABLED", True)
    monkeypatch.setattr(settings, "RQ_MAX_RETRIES", 2)
    monkeypatch.setattr(settings, "RQ_RETRY_INTERVAL_SECONDS", 1)
    ProcessingQueueService._local_locks.clear()


def _submission_kwargs(content: bytes = b"phase-4-cv") -> dict[str, str | None]:
    return {
        "cv_key": "cv_phase_4",
        "content_hash": hashlib.sha256(content).hexdigest(),
        "filename": "phase_4.pdf",
        "storage_filename": f"cv_phase_4_{hashlib.sha256(content).hexdigest()}.pdf",
        "content_type": "application/pdf",
    }


def test_job_is_persisted_before_rq_enqueue_and_duplicate_submission_is_idempotent(monkeypatch):
    enqueued: list[str] = []

    class FakeQueue:
        def __init__(self, *_args, **_kwargs):
            pass

        def enqueue(self, _function, processing_job_id, **_kwargs):
            persisted = ProcessingJobRepository.get(processing_job_id)
            assert persisted is not None
            assert persisted.state == JobState.QUEUED
            assert persisted.execution_mode == ProcessingExecutionMode.RQ
            enqueued.append(processing_job_id)

    monkeypatch.setattr(ProcessingQueueService, "_redis_connection", staticmethod(lambda: object()))
    monkeypatch.setattr(ProcessingQueueService, "_job_lock", classmethod(lambda _cls, *_args: nullcontext()))
    monkeypatch.setattr(processing_queue, "Queue", FakeQueue)

    first = ProcessingQueueService.submit_upload(**_submission_kwargs())
    second = ProcessingQueueService.submit_upload(**_submission_kwargs())

    assert first.record.job_id == second.record.job_id
    assert second.reused_existing_job is True
    assert enqueued == [first.record.job_id]


def test_changed_content_gets_an_isolated_processing_job(monkeypatch):
    monkeypatch.setattr(ProcessingQueueService, "_redis_connection", staticmethod(lambda: None))
    monkeypatch.setattr(ProcessingQueueService, "_job_lock", classmethod(lambda _cls, *_args: nullcontext()))

    first = ProcessingQueueService.submit_upload(**_submission_kwargs(b"version-one"))
    second = ProcessingQueueService.submit_upload(**_submission_kwargs(b"version-two"))

    assert first.record.job_id != second.record.job_id
    assert first.schedule_development_fallback is True
    assert second.schedule_development_fallback is True


def test_duplicate_force_reprocess_reuses_an_active_job(monkeypatch):
    monkeypatch.setattr(ProcessingQueueService, "_redis_connection", staticmethod(lambda: None))
    monkeypatch.setattr(ProcessingQueueService, "_job_lock", classmethod(lambda _cls, *_args: nullcontext()))

    first = ProcessingQueueService.submit_upload(**_submission_kwargs(), force_reprocess=True)
    second = ProcessingQueueService.submit_upload(**_submission_kwargs(), force_reprocess=True)

    assert first.record.job_id == second.record.job_id
    assert second.reused_existing_job is True


def test_redis_outage_uses_only_the_explicit_development_fallback(monkeypatch):
    monkeypatch.setattr(ProcessingQueueService, "_redis_connection", staticmethod(lambda: None))
    monkeypatch.setattr(ProcessingQueueService, "_job_lock", classmethod(lambda _cls, *_args: nullcontext()))

    submission = ProcessingQueueService.submit_upload(**_submission_kwargs())

    assert submission.schedule_development_fallback is True
    assert submission.record.execution_mode == ProcessingExecutionMode.DEVELOPMENT_FALLBACK
    assert submission.record.state == JobState.QUEUED


def test_production_redis_outage_fails_instead_of_using_fastapi_background_tasks(monkeypatch):
    from app.services.processing_queue import ProcessingQueueUnavailableError

    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "RQ_DEVELOPMENT_FALLBACK_ENABLED", False)
    monkeypatch.setattr(ProcessingQueueService, "_redis_connection", staticmethod(lambda: None))
    monkeypatch.setattr(ProcessingQueueService, "_job_lock", classmethod(lambda _cls, *_args: nullcontext()))

    with pytest.raises(ProcessingQueueUnavailableError):
        ProcessingQueueService.submit_upload(**_submission_kwargs())

    failed = ProcessingJobRepository.get_by_cv_key("cv_phase_4")
    assert failed is not None
    assert failed.state == JobState.FAILED
    assert failed.stage == "enqueue"


def test_worker_revalidates_source_and_persists_completion(monkeypatch, tmp_path):
    content = b"phase-4-cv"
    monkeypatch.setattr(ProcessingQueueService, "_redis_connection", staticmethod(lambda: None))
    monkeypatch.setattr(ProcessingQueueService, "_job_lock", classmethod(lambda _cls, *_args: nullcontext()))
    submission = ProcessingQueueService.submit_upload(**_submission_kwargs(content))
    source = StoredUpload(
        safe_filename="phase_4.pdf",
        storage_filename=submission.record.storage_filename,
        detected_content_type="application/pdf",
        content=content,
        path=Path(tmp_path / submission.record.storage_filename),
    )
    monkeypatch.setattr(UploadService, "load_reprocessable_upload", lambda **_kwargs: source)

    async def fake_process_source(**_kwargs):
        return {"status": "NEW_CV", "message": "complete"}

    monkeypatch.setattr(processing_queue, "_process_source", fake_process_source)

    process_cv_job(submission.record.job_id)

    completed = ProcessingJobRepository.get(submission.record.job_id)
    assert completed is not None
    assert completed.state == JobState.COMPLETED
    assert completed.progress == 100
    assert completed.attempt == 1


def test_worker_marks_retry_state_before_rq_rethrows(monkeypatch):
    content = b"phase-4-cv"
    monkeypatch.setattr(ProcessingQueueService, "_redis_connection", staticmethod(lambda: None))
    monkeypatch.setattr(ProcessingQueueService, "_job_lock", classmethod(lambda _cls, *_args: nullcontext()))
    submission = ProcessingQueueService.submit_upload(**_submission_kwargs(content))
    source = StoredUpload(
        safe_filename="phase_4.pdf",
        storage_filename=submission.record.storage_filename,
        detected_content_type="application/pdf",
        content=content,
        path=Path(submission.record.storage_filename),
    )
    monkeypatch.setattr(UploadService, "load_reprocessable_upload", lambda **_kwargs: source)

    async def fail_processing(**_kwargs):
        raise RuntimeError("transient parser failure")

    monkeypatch.setattr(processing_queue, "_process_source", fail_processing)

    with pytest.raises(RuntimeError, match="transient parser failure"):
        process_cv_job(submission.record.job_id)

    retrying = ProcessingJobRepository.get(submission.record.job_id)
    assert retrying is not None
    assert retrying.state == JobState.RETRYING
    assert retrying.attempt == 1
    assert retrying.error is not None
    assert retrying.error.retryable is True


@pytest.mark.asyncio
@pytest.mark.parametrize("status_handler", ["cv", "match"])
async def test_unknown_polling_job_returns_real_not_found_after_compatibility_period(monkeypatch, status_handler):
    from app.api.analysis import get_match_status
    from app.api.cv import get_cv_status

    monkeypatch.setattr(ResultRepository, "resolve_result", lambda _key: None)
    monkeypatch.setattr(ProcessingJobRepository, "get_by_cv_key", lambda _key: None)
    monkeypatch.setattr(settings, "JOB_NOT_FOUND_COMPATIBILITY_UNTIL", None)
    handler = get_cv_status if status_handler == "cv" else get_match_status

    with pytest.raises(HTTPException) as exc_info:
        await handler("cv_unknown")

    assert exc_info.value.status_code == 404
