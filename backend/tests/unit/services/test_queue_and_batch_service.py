from __future__ import annotations

from unittest.mock import Mock, patch

from app.core.config import settings
from app.schemas.contracts import JobState, ProcessingExecutionMode, ProcessingJobRecord
from app.services.processing_queue import ProcessingQueueService, QueueSubmission
from app.services.shadow_validation_service import ShadowValidationService


def test_queue_submission_dataclass() -> None:
    record = ProcessingJobRecord(
        job_id="job-uuid-101",
        cv_key="cv-hash-101",
        content_hash="content-sha256-101",
        filename="resume.pdf",
        storage_filename="storage_resume.pdf",
        parser_version="1.0.0",
        schema_version="1.0.0",
        state=JobState.QUEUED,
        progress=0,
        stage="QUEUED",
        message="Job queued for processing",
        execution_mode=ProcessingExecutionMode.RQ,
        attempt=0,
        max_attempts=3,
    )
    submission = QueueSubmission(record=record, reused_existing_job=False)
    assert submission.record.job_id == "job-uuid-101"
    assert submission.record.state == JobState.QUEUED
    assert submission.reused_existing_job is False


def test_processing_job_record_state_transitions() -> None:
    record = ProcessingJobRecord(
        job_id="job-uuid-102",
        cv_key="cv-hash-102",
        content_hash="content-sha256-102",
        filename="cv.docx",
        storage_filename="storage_cv.docx",
        parser_version="1.0.0",
        schema_version="1.0.0",
        state=JobState.PROCESSING,
        progress=50,
        stage="EXTRACTION",
        message="Extracting resume sections",
        execution_mode=ProcessingExecutionMode.RQ,
        attempt=0,
        max_attempts=3,
    )
    assert record.progress == 50
    assert record.state == JobState.PROCESSING


def test_shadow_validation_uses_configured_queue_and_retry_policy(monkeypatch) -> None:
    monkeypatch.setattr(settings, "REDIS_URL", "redis://shadow.example/0")
    monkeypatch.setattr(settings, "RQ_SHADOW_QUEUE_NAME", "tenant-shadow")
    monkeypatch.setattr(settings, "SHADOW_VALIDATION_MAX_RETRIES", 4, raising=False)
    monkeypatch.setattr(settings, "SHADOW_VALIDATION_RETRY_INTERVAL_SECONDS", 45, raising=False)
    monkeypatch.setattr(settings, "SHADOW_VALIDATION_JOB_TIMEOUT_SECONDS", 720, raising=False)
    connection = object()

    with (
        patch("redis.Redis.from_url", return_value=connection),
        patch("rq.Queue") as queue_type,
        patch("rq.Retry", return_value="retry-policy") as retry_type,
    ):
        queued = ShadowValidationService.enqueue_shadow_validation(
            101,
            202,
            {"score": 80},
            "synthetic CV text",
        )

    assert queued is True
    queue_type.assert_called_once_with("tenant-shadow", connection=connection)
    retry_type.assert_called_once_with(max=4, interval=45)
    enqueue_kwargs = queue_type.return_value.enqueue.call_args.kwargs
    assert enqueue_kwargs["retry"] == "retry-policy"
    assert enqueue_kwargs["job_timeout"] == 720


def test_processing_queue_redis_probe_uses_configured_timeout(monkeypatch) -> None:
    monkeypatch.setattr(settings, "REDIS_URL", "redis://queue.example/0")
    monkeypatch.setattr(settings, "REDIS_AVAILABILITY_PROBE_TIMEOUT_SECONDS", 2.5, raising=False)
    connection = Mock()

    with patch("app.services.processing_queue.Redis.from_url", return_value=connection) as from_url:
        assert ProcessingQueueService._redis_connection() is connection

    from_url.assert_called_once_with(
        settings.REDIS_URL,
        socket_connect_timeout=2.5,
        socket_timeout=2.5,
    )


def test_submission_lock_uses_configured_blocking_timeout(monkeypatch) -> None:
    monkeypatch.setattr(settings, "REDIS_LOCK_BLOCKING_TIMEOUT_SECONDS", 7)
    connection = Mock()
    lock = connection.lock.return_value
    lock.acquire.return_value = True

    with ProcessingQueueService._submission_lock(connection):
        pass

    connection.lock.assert_called_once_with(
        ProcessingQueueService._SUBMISSION_LOCK_KEY,
        timeout=settings.PROCESSING_JOB_LOCK_TIMEOUT_SECONDS,
        blocking_timeout=7,
    )
