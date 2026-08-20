from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.core.config import settings
from app.schemas.contracts import ErrorCode, JobState, ProcessingExecutionMode, ProcessingJobRecord
from app.services.processing_queue import ProcessingQueueService, QueueSubmission, handle_work_horse_killed
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


def test_abandoned_rq_job_is_classified_as_worker_lost_and_terminal_result_is_synchronized() -> None:
    record = ProcessingJobRecord(
        job_id="cvjob-abandoned",
        cv_key="cv-abandoned",
        content_hash="content-sha256-abandoned",
        filename="resume.pdf",
        storage_filename="stored-resume.pdf",
        parser_version="1.0.0",
        schema_version="1.0.0",
        state=JobState.PROCESSING,
        progress=75,
        stage="matching",
        message="Matching vacancies",
        execution_mode=ProcessingExecutionMode.RQ,
        rq_job_id="cvjob-abandoned-1",
        attempt=3,
        max_attempts=3,
    )
    rq_job = Mock()
    rq_job.get_status.return_value = "failed"
    rq_job.latest_result.return_value = SimpleNamespace(
        exc_string="Moved to FailedJobRegistry, due to AbandonedJobError",
    )
    connection = Mock()
    connection.lock.return_value.acquire.return_value = True
    saved_results: list[dict] = []

    def transition(_job_id: str, state: str, **updates):
        return record.model_copy(update={"state": state, **updates})

    with (
        patch("rq.job.Job.fetch", return_value=rq_job),
        patch("app.services.processing_queue.ProcessingJobRepository.get", return_value=record),
        patch("app.services.processing_queue.ProcessingJobRepository.transition", side_effect=transition),
        patch(
            "app.services.processing_queue.ResultRepository.resolve_result",
            return_value={
                "id": "cv-abandoned",
                "status": "processing",
                "stage": "matching",
                "progress": 75,
                "resume_json": {"skills": ["Python"]},
                "result_generation_id": "gen-existing",
            },
        ),
        patch(
            "app.services.processing_queue.ResultRepository.atomic_save_result",
            side_effect=lambda _filename, data: saved_results.append(dict(data)) or "saved",
        ),
    ):
        reconciled = ProcessingQueueService.reconcile_job(record, connection=connection, allow_recovery=True)

    assert reconciled.state == JobState.FAILED
    assert reconciled.stage == "worker_lost"
    assert reconciled.error is not None
    assert reconciled.error.code == ErrorCode.WORKER_LOST
    assert reconciled.error.details == {"failure_type": "AbandonedJobError"}
    assert len(saved_results) == 1
    saved = saved_results[0]
    assert saved["status"] == "FAILED"
    assert saved["progress"] == 100
    assert saved["stage"] == "worker_lost"
    assert saved["error_code"] == "WORKER_LOST"
    assert saved["failure_metadata"] == {"failure_type": "AbandonedJobError"}
    assert saved["resume_json"] == {"skills": ["Python"]}
    assert saved["result_generation_id"] == "gen-existing"


def test_abandoned_rq_job_with_attempts_remaining_is_recovered() -> None:
    record = ProcessingJobRecord(
        job_id="cvjob-recoverable",
        cv_key="cv-recoverable",
        content_hash="content-sha256-recoverable",
        filename="resume.pdf",
        storage_filename="stored-resume.pdf",
        parser_version="1.0.0",
        schema_version="1.0.0",
        state=JobState.PROCESSING,
        progress=75,
        stage="matching",
        message="Matching vacancies",
        execution_mode=ProcessingExecutionMode.RQ,
        rq_job_id="cvjob-recoverable-1",
        attempt=1,
        max_attempts=3,
        enqueue_count=1,
    )
    rq_job = Mock()
    rq_job.get_status.return_value = "failed"
    rq_job.latest_result.return_value = SimpleNamespace(
        exc_string="Moved to FailedJobRegistry, due to AbandonedJobError",
    )
    connection = Mock()
    connection.lock.return_value.acquire.return_value = True

    def transition(_job_id: str, state: str, **updates):
        return record.model_copy(update={"state": state, **updates})

    with (
        patch("rq.job.Job.fetch", return_value=rq_job),
        patch("app.services.processing_queue.ProcessingJobRepository.get", return_value=record),
        patch("app.services.processing_queue.ProcessingJobRepository.transition", side_effect=transition),
        patch.object(ProcessingQueueService, "_enqueue_record") as enqueue_record,
        patch("app.services.processing_queue.ResultRepository.atomic_save_result") as save_result,
    ):
        reconciled = ProcessingQueueService.reconcile_job(record, connection=connection, allow_recovery=True)

    assert reconciled.state == JobState.RETRYING
    assert reconciled.stage == "recovered_queue"
    assert reconciled.error is not None
    assert reconciled.error.code == ErrorCode.WORKER_LOST
    assert reconciled.rq_job_id == "cvjob-recoverable-2"
    enqueue_record.assert_called_once()
    save_result.assert_not_called()


def test_terminal_workhorse_crash_synchronizes_failed_result() -> None:
    record = ProcessingJobRecord(
        job_id="cvjob-workhorse",
        cv_key="cv-workhorse",
        content_hash="content-sha256-workhorse",
        filename="resume.pdf",
        storage_filename="stored-resume.pdf",
        parser_version="1.0.0",
        schema_version="1.0.0",
        state=JobState.PROCESSING,
        progress=60,
        stage="extraction",
        message="Extracting resume",
        execution_mode=ProcessingExecutionMode.RQ,
        rq_job_id="cvjob-workhorse-1",
        attempt=3,
        max_attempts=3,
    )
    rq_job = SimpleNamespace(args=(record.job_id,), retries_left=0, id=record.rq_job_id)
    saved_results: list[dict] = []

    def transition(_job_id: str, state: str, **updates):
        return record.model_copy(update={"state": state, **updates})

    with (
        patch("app.services.processing_queue.ProcessingJobRepository.get", return_value=record),
        patch("app.services.processing_queue.ProcessingJobRepository.transition", side_effect=transition),
        patch("app.services.processing_queue.ResultRepository.resolve_result", return_value=None),
        patch(
            "app.services.processing_queue.ResultRepository.atomic_save_result",
            side_effect=lambda _filename, data: saved_results.append(dict(data)) or "saved",
        ),
    ):
        handle_work_horse_killed(rq_job, None, None, None)

    assert len(saved_results) == 1
    assert saved_results[0]["status"] == "FAILED"
    assert saved_results[0]["stage"] == "worker_crash"
    assert saved_results[0]["error_code"] == "WORKER_LOST"
