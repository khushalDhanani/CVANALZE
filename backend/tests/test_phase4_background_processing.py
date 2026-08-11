import hashlib
from contextlib import nullcontext
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
from rq.job import Job, NoSuchJobError

from app.core.cache import MemoryCache, cv_result_cache_manager, processing_job_cache_manager
from app.core.config import settings
from app.repositories import result as result_repository_module
from app.repositories import processing_job as processing_job_repository_module
from app.repositories.processing_job import ProcessingJobRepository
from app.repositories.result import ResultRepository
from app.schemas.contracts import JobState, ProcessingExecutionMode
from app.services import processing_queue
from app.services.processing_queue import (
    ProcessingQueueFullError,
    ProcessingQueueService,
    ProcessingQueueUnavailableError,
    handle_work_horse_killed,
    process_cv_job,
)
from app.services.upload_service import StoredUpload, UploadService


@pytest.fixture(autouse=True)
def isolate_processing_jobs(monkeypatch):
    monkeypatch.setattr(processing_job_repository_module, "PostgresAppSession", None)
    monkeypatch.setattr(processing_job_cache_manager, "_providers", [MemoryCache(max_size=100)])
    monkeypatch.setattr(settings, "RQ_MAX_RETRIES", 2)
    monkeypatch.setattr(settings, "RQ_RETRY_INTERVAL_SECONDS", 1)
    monkeypatch.setattr(settings, "CV_QUEUE_MAX_SIZE", 1000)
    monkeypatch.setattr(ProcessingQueueService, "_redis_connection", staticmethod(lambda: object()))
    monkeypatch.setattr(ProcessingQueueService, "_submission_lock", classmethod(lambda _cls, *_args: nullcontext()))
    monkeypatch.setattr(ProcessingQueueService, "_queue_load", staticmethod(lambda *_args: 0))

    class FakeQueue:
        def __init__(self, *_args, **_kwargs):
            pass

        def enqueue(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(processing_queue, "Queue", FakeQueue)


def _submission_kwargs(content: bytes = b"phase-4-cv") -> dict[str, Any]:
    return {
        "cv_key": "cv_phase_4",
        "content_hash": hashlib.sha256(content).hexdigest(),
        "filename": "phase_4.pdf",
        "storage_filename": f"cv_phase_4_{hashlib.sha256(content).hexdigest()}.pdf",
        "content_type": "application/pdf",
    }


def test_job_is_persisted_before_rq_enqueue_and_duplicate_submission_is_idempotent(
    monkeypatch,
):
    enqueued: list[tuple[str, dict[str, Any]]] = []

    class FakeQueue:
        def __init__(self, *_args, **_kwargs):
            pass

        def enqueue(self, _function, processing_job_id, _enqueue_count, **kwargs):
            persisted = ProcessingJobRepository.get(processing_job_id)
            assert persisted is not None
            assert persisted.state == JobState.QUEUED
            assert persisted.execution_mode == ProcessingExecutionMode.RQ
            enqueued.append((processing_job_id, kwargs))

    monkeypatch.setattr(processing_queue, "Queue", FakeQueue)

    first = ProcessingQueueService.submit_upload(**_submission_kwargs())
    second = ProcessingQueueService.submit_upload(**_submission_kwargs())

    assert first.record.job_id == second.record.job_id
    assert second.reused_existing_job is True
    assert [item[0] for item in enqueued] == [first.record.job_id]
    assert enqueued[0][1]["unique"] is True


def test_changed_content_gets_an_isolated_processing_job(monkeypatch):
    first = ProcessingQueueService.submit_upload(**_submission_kwargs(b"version-one"))
    second = ProcessingQueueService.submit_upload(**_submission_kwargs(b"version-two"))

    assert first.record.job_id != second.record.job_id
    assert first.record.execution_mode == ProcessingExecutionMode.RQ
    assert second.record.execution_mode == ProcessingExecutionMode.RQ


def test_duplicate_force_reprocess_reuses_an_active_job(monkeypatch):
    first = ProcessingQueueService.submit_upload(**_submission_kwargs(), force_reprocess=True)
    second = ProcessingQueueService.submit_upload(**_submission_kwargs(), force_reprocess=True)

    assert first.record.job_id == second.record.job_id
    assert second.reused_existing_job is True


def test_missing_processing_rq_job_is_failed(monkeypatch):
    submission = ProcessingQueueService.submit_upload(**_submission_kwargs())
    missing = ProcessingJobRepository.save(
        submission.record.model_copy(
            update={
                "state": JobState.PROCESSING,
                "execution_mode": ProcessingExecutionMode.RQ,
                "rq_job_id": f"{submission.record.job_id}-1",
            }
        )
    )
    monkeypatch.setattr(Job, "fetch", lambda *_args, **_kwargs: (_ for _ in ()).throw(NoSuchJobError()))

    reconciled = ProcessingQueueService.reconcile_job(missing, connection=object())

    assert reconciled.state == JobState.FAILED
    assert reconciled.progress == 100
    assert reconciled.stage == "missing_queue_job"
    assert reconciled.error is not None
    assert reconciled.error.retryable is True


def test_newly_queued_job_has_visibility_grace_when_rq_job_is_not_visible(monkeypatch):
    submission = ProcessingQueueService.submit_upload(**_submission_kwargs())
    queued = ProcessingJobRepository.save(
        submission.record.model_copy(
            update={
                "execution_mode": ProcessingExecutionMode.RQ,
                "rq_job_id": f"{submission.record.job_id}-1",
            }
        )
    )
    monkeypatch.setattr(Job, "fetch", lambda *_args, **_kwargs: (_ for _ in ()).throw(NoSuchJobError()))

    reconciled = ProcessingQueueService.reconcile_job(queued, connection=object())

    assert reconciled.state == JobState.QUEUED


def test_missing_processing_job_is_idempotently_requeued_by_recovery(monkeypatch):
    submission = ProcessingQueueService.submit_upload(**_submission_kwargs())
    processing = ProcessingJobRepository.save(
        submission.record.model_copy(
            update={
                "state": JobState.PROCESSING,
                "attempt": 1,
                "updated_at": submission.record.updated_at - timedelta(minutes=5),
            }
        )
    )
    enqueued = []

    class Lock:
        @staticmethod
        def acquire(**_kwargs):
            return True

        @staticmethod
        def release():
            return None

    class Connection:
        @staticmethod
        def lock(*_args, **_kwargs):
            return Lock()

    class RecoveryQueue:
        def __init__(self, *_args, **_kwargs):
            pass

        def enqueue(self, _function, job_id, enqueue_count, **options):
            enqueued.append((job_id, enqueue_count, options["job_id"]))

    monkeypatch.setattr(Job, "fetch", lambda *_args, **_kwargs: (_ for _ in ()).throw(NoSuchJobError()))
    monkeypatch.setattr(processing_queue, "Queue", RecoveryQueue)

    recovered = ProcessingQueueService.reconcile_job(processing, connection=Connection(), allow_recovery=True)

    assert recovered.state == JobState.RETRYING
    assert recovered.stage == "recovered_queue"
    assert recovered.error is not None
    assert recovered.error.retryable is True
    assert enqueued == [(recovered.job_id, recovered.enqueue_count, recovered.rq_job_id)]


def test_job_listing_reconciles_and_preserves_fifo_sequence(monkeypatch):
    first = ProcessingQueueService.submit_upload(**_submission_kwargs(b"first"))
    second = ProcessingQueueService.submit_upload(**_submission_kwargs(b"second"))
    records = [
        second.record.model_copy(update={"enqueue_sequence": 2}),
        first.record.model_copy(update={"enqueue_sequence": 1}),
    ]
    monkeypatch.setattr(ProcessingJobRepository, "list_recent", lambda **_kwargs: records)
    monkeypatch.setattr(ProcessingQueueService, "reconcile_job", classmethod(lambda _cls, record, **_kwargs: record))

    listed = ProcessingQueueService.list_jobs()

    assert [record.job_id for record in listed] == [first.record.job_id, second.record.job_id]


@pytest.mark.parametrize(
    ("rq_status", "expected_state"),
    [("queued", JobState.RETRYING), ("scheduled", JobState.RETRYING), ("canceled", JobState.CANCELLED)],
)
def test_rq_recovery_states_are_reflected_in_the_canonical_job(monkeypatch, rq_status, expected_state):
    submission = ProcessingQueueService.submit_upload(**_submission_kwargs())
    processing = ProcessingJobRepository.save(submission.record.model_copy(update={"state": JobState.PROCESSING}))

    class RQJob:
        @staticmethod
        def get_status(refresh=True):
            assert refresh is True
            return rq_status

    monkeypatch.setattr(Job, "fetch", lambda *_args, **_kwargs: RQJob())

    reconciled = ProcessingQueueService.reconcile_job(processing, connection=object())

    assert reconciled.state == expected_state


def test_duplicate_submission_requeues_a_missing_processing_job(monkeypatch):
    first = ProcessingQueueService.submit_upload(**_submission_kwargs())
    ProcessingJobRepository.save(
        first.record.model_copy(
            update={
                "state": JobState.PROCESSING,
                "execution_mode": ProcessingExecutionMode.RQ,
                "rq_job_id": f"{first.record.job_id}-1",
                "updated_at": first.record.updated_at - timedelta(minutes=1),
            }
        )
    )
    enqueued: list[str] = []

    class FakeQueue:
        def __init__(self, *_args, **_kwargs):
            pass

        def enqueue(self, _function, _processing_job_id, _enqueue_count, **options):
            enqueued.append(options["job_id"])

    monkeypatch.setattr(ProcessingQueueService, "_redis_connection", staticmethod(lambda: object()))
    monkeypatch.setattr(Job, "fetch", lambda *_args, **_kwargs: (_ for _ in ()).throw(NoSuchJobError()))
    monkeypatch.setattr(processing_queue, "Queue", FakeQueue)

    retried = ProcessingQueueService.submit_upload(**_submission_kwargs())

    assert retried.reused_existing_job is False
    assert retried.record.state == JobState.QUEUED
    assert retried.record.enqueue_count == 2
    assert enqueued == [f"{retried.record.job_id}-2"]


def test_redis_outage_never_executes_cv_processing_in_fastapi(monkeypatch):
    monkeypatch.setattr(ProcessingQueueService, "_redis_connection", staticmethod(lambda: None))

    with pytest.raises(ProcessingQueueUnavailableError, match="was not queued"):
        ProcessingQueueService.submit_upload(**_submission_kwargs())


def test_production_redis_outage_fails_instead_of_using_fastapi_background_tasks(
    monkeypatch,
):
    monkeypatch.setattr(ProcessingQueueService, "_redis_connection", staticmethod(lambda: None))

    with pytest.raises(ProcessingQueueUnavailableError):
        ProcessingQueueService.submit_upload(**_submission_kwargs())

    failed = ProcessingJobRepository.get_by_cv_key("cv_phase_4")
    assert failed is None


def test_queue_capacity_rejects_new_work_but_reuses_duplicates(monkeypatch):
    first = ProcessingQueueService.submit_upload(**_submission_kwargs())
    monkeypatch.setattr(ProcessingQueueService, "_queue_load", staticmethod(lambda *_args: settings.CV_QUEUE_MAX_SIZE))

    duplicate = ProcessingQueueService.submit_upload(**_submission_kwargs())
    assert duplicate.record.job_id == first.record.job_id
    assert duplicate.reused_existing_job is True

    with pytest.raises(ProcessingQueueFullError, match="CV_QUEUE_FULL"):
        ProcessingQueueService.submit_upload(**_submission_kwargs(b"queue-overflow"))


def test_ten_cv_jobs_execute_fifo_with_only_one_processing_state(monkeypatch, tmp_path):
    rq_order: list[str] = []

    class OrderedQueue:
        def __init__(self, *_args, **_kwargs):
            pass

        def enqueue(self, _function, processing_job_id, _enqueue_count, **_kwargs):
            rq_order.append(processing_job_id)

    monkeypatch.setattr(processing_queue, "Queue", OrderedQueue)
    submissions = [
        ProcessingQueueService.submit_upload(**_submission_kwargs(f"cv-{index}".encode("utf-8")))
        for index in range(10)
    ]
    job_ids = [submission.record.job_id for submission in submissions]
    assert rq_order == job_ids
    assert all(ProcessingJobRepository.get(job_id).state == JobState.QUEUED for job_id in job_ids)

    content_by_job = {submission.record.job_id: f"cv-{index}".encode("utf-8") for index, submission in enumerate(submissions)}

    def load_source(**kwargs):
        job_id = next(job_id for job_id in job_ids if ProcessingJobRepository.get(job_id).storage_filename == kwargs["storage_filename"])
        content = content_by_job[job_id]
        return StoredUpload(
            safe_filename="phase_4.pdf",
            storage_filename=kwargs["storage_filename"],
            detected_content_type="application/pdf",
            content=content,
            path=Path(tmp_path / kwargs["storage_filename"]),
        )

    async def observe_single_lane(**kwargs):
        states = [ProcessingJobRepository.get(job_id).state for job_id in job_ids]
        assert states.count(JobState.PROCESSING) == 1
        current_index = job_ids.index(kwargs["record"].job_id)
        assert all(state == JobState.COMPLETED for state in states[:current_index])
        assert all(state == JobState.QUEUED for state in states[current_index + 1:])
        return {"status": "NEW_CV", "message": "complete"}

    monkeypatch.setattr(UploadService, "load_reprocessable_upload", load_source)
    monkeypatch.setattr(processing_queue, "_process_source", observe_single_lane)
    for job_id in rq_order:
        process_cv_job(job_id)

    assert all(ProcessingJobRepository.get(job_id).state == JobState.COMPLETED for job_id in job_ids)


def test_worker_revalidates_source_and_persists_completion(monkeypatch, tmp_path):
    content = b"phase-4-cv"
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


def test_worker_exposes_postgres_persistence_failure_as_degraded_completion(monkeypatch, tmp_path):
    content = b"phase-4-cv"
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
        return {
            "status": "COMPLETED_DEGRADED",
            "persistence_status": "degraded",
            "persistence_error": "PostgreSQL result persistence failed.",
        }

    monkeypatch.setattr(processing_queue, "_process_source", fake_process_source)

    process_cv_job(submission.record.job_id)

    completed = ProcessingJobRepository.get(submission.record.job_id)
    assert completed is not None
    assert completed.state == JobState.COMPLETED_DEGRADED
    assert completed.stage == "complete_degraded"
    assert completed.progress == 100
    assert completed.error is not None
    assert completed.error.retryable is True


def test_result_repository_marks_postgres_failure_and_keeps_fallback(monkeypatch, tmp_path):
    filename = "cv_persistence_failure.json"
    result_data = {
        "id": "cv_persistence_failure",
        "status": "COMPLETED",
        "full_name": "Fallback Candidate",
    }

    def fail_postgres_session():
        raise RuntimeError("postgres unavailable")

    monkeypatch.setattr(result_repository_module, "PostgresAppSession", fail_postgres_session)
    monkeypatch.setattr(settings, "RESULTS_DIR", tmp_path)

    ResultRepository.atomic_save_result(filename, result_data)

    assert result_data["status"] == "COMPLETED_DEGRADED"
    assert result_data["persistence_status"] == ResultRepository.PERSISTENCE_DEGRADED
    assert result_data["persistence_error"] == ResultRepository.PERSISTENCE_ERROR_MESSAGE
    assert cv_result_cache_manager.get(filename)["status"] == "COMPLETED_DEGRADED"
    assert (tmp_path / filename).is_file()
    cv_result_cache_manager.delete(filename)


def test_worker_marks_retry_state_before_rq_rethrows(monkeypatch):
    content = b"phase-4-cv"
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


def test_workhorse_crash_marks_job_retrying_without_blocking_the_worker():
    submission = ProcessingQueueService.submit_upload(**_submission_kwargs())
    ProcessingJobRepository.transition(submission.record.job_id, JobState.PROCESSING)
    rq_job = type("RQJob", (), {"args": (submission.record.job_id,), "retries_left": 1})()

    handle_work_horse_killed(rq_job, 123, 9, None)

    retrying = ProcessingJobRepository.get(submission.record.job_id)
    assert retrying is not None
    assert retrying.state == JobState.RETRYING
    assert retrying.error is not None
    assert retrying.error.retryable is True
    payload = ProcessingQueueService.legacy_status_payload(retrying)
    assert payload["error_code"] == "PROCESSING_FAILED"
    assert payload["error_message"] == "The CV processing workhorse terminated unexpectedly."
    assert payload["error_details"] is None


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
