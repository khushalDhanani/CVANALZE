from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.cache import MemoryCache, processing_job_cache_manager
from app.core.config import settings
from app.repositories.batch_job import BatchJobRepository
from app.repositories.processing_job import ProcessingJobRepository
from app.repositories.result import ResultRepository
from app.schemas.batch import BatchJobItem, BatchJobRecord
from app.schemas.contracts import JobState
from app.services import batch_processing_service
from app.services.batch_processing_service import BatchProcessingService, process_batch_job
from app.services.processing_queue import ProcessingQueueService
from app.services.upload_service import AcceptedUpload, StoredUpload, UploadService


@pytest.fixture(autouse=True)
def isolate_batch_jobs(monkeypatch):
    monkeypatch.setattr(processing_job_cache_manager, "_providers", [MemoryCache(max_size=100)])
    monkeypatch.setattr(settings, "RQ_MAX_RETRIES", 0)


def test_batch_submission_enqueues_one_rq_coordinator(monkeypatch):
    enqueued = []

    class FakeQueue:
        def __init__(self, *_args, **_kwargs):
            pass

        def enqueue(self, function, batch_job_id, **options):
            enqueued.append((function, batch_job_id, options))

    monkeypatch.setattr(ProcessingQueueService, "_redis_connection", staticmethod(lambda: object()))
    monkeypatch.setattr(batch_processing_service, "Queue", FakeQueue)

    record = BatchProcessingService.submit(5)

    assert record.state == "QUEUED"
    assert len(enqueued) == 1
    assert enqueued[0][0] is process_batch_job
    assert enqueued[0][1] == record.batch_job_id


def test_batch_worker_queues_binary_cv_through_standard_processing_pipeline(monkeypatch, tmp_path):
    record = BatchJobRepository.save(BatchJobRecord(batch_job_id="batch_pipeline", limit=1))
    candidate = SimpleNamespace(
        CandidateID=42,
        CandidateFirstName="Ada",
        CandidateLastName="Lovelace",
        CandidateCVFileName="candidate.pdf",
    )

    class FakeResult:
        @staticmethod
        def scalars():
            return SimpleNamespace(all=lambda: [candidate])

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def execute(_statement):
            return FakeResult()

    source = StoredUpload(
        safe_filename="candidate.pdf",
        storage_filename="candidate.pdf",
        detected_content_type="application/pdf",
        content=b"%PDF-1.7 binary cv",
        path=Path(tmp_path / "candidate.pdf"),
    )
    retained = AcceptedUpload(
        original_filename="candidate.pdf",
        safe_filename="candidate.pdf",
        storage_filename=f"cv_candidate_42_{'a' * 64}.pdf",
        extension="pdf",
        declared_content_type="application/pdf",
        detected_content_type="application/pdf",
        content_hash="a" * 64,
        content=source.content,
        path=Path(tmp_path / "retained.pdf"),
        was_already_stored=False,
    )
    submitted = []
    monkeypatch.setattr(batch_processing_service, "MssqlReadSession", FakeSession)
    monkeypatch.setattr(UploadService, "load_reprocessable_upload", lambda **_kwargs: source)
    monkeypatch.setattr(UploadService, "persist_bytes", lambda **_kwargs: retained)
    monkeypatch.setattr(
        ProcessingQueueService,
        "submit_upload",
        lambda **kwargs: submitted.append(kwargs)
        or SimpleNamespace(
            record=SimpleNamespace(job_id="cv_job_42"),
            schedule_development_fallback=False,
        ),
    )

    result = process_batch_job(record.batch_job_id)
    process_batch_job(record.batch_job_id)

    queued = BatchJobRepository.get(record.batch_job_id)
    assert result["queued"] == 1
    assert queued is not None
    assert queued.stage == "cv_jobs_queued"
    assert len(submitted) == 1
    assert submitted[0]["cv_key"] == "cv_candidate_42"
    assert submitted[0]["source_candidate_id"] == 42
    assert submitted[0]["storage_filename"] == retained.storage_filename


def test_batch_status_aggregates_normal_cv_job_results(monkeypatch):
    record = BatchJobRecord(
        batch_job_id="batch_status",
        limit=1,
        state="PROCESSING",
        stage="cv_jobs_queued",
        total=1,
        items=[
            BatchJobItem(
                candidate_id=42,
                candidate_name="Ada Lovelace",
                filename="candidate.pdf",
                cv_key="cv_candidate_42",
                processing_job_id="cv_job_42",
            )
        ],
    )
    BatchJobRepository.save(record)
    monkeypatch.setattr(
        ProcessingJobRepository,
        "get",
        lambda _job_id: SimpleNamespace(state=JobState.COMPLETED, message="complete"),
    )
    monkeypatch.setattr(
        ResultRepository,
        "resolve_result",
        lambda _cv_key: {"match_analysis": {"best_match": {"job_title": "Engineer"}}},
    )
    reconcile_calls = []
    monkeypatch.setattr(
        ProcessingQueueService,
        "reconcile_job",
        lambda child: reconcile_calls.append(child) or child,
    )

    completed = BatchProcessingService.get_status(record.batch_job_id)

    assert completed is not None
    assert completed.state == "COMPLETED"
    assert completed.progress == 100
    assert completed.matches[0]["analysis"]["best_match"]["job_title"] == "Engineer"
    assert len(reconcile_calls) == 1


def test_batch_status_marks_failed_coordinator_terminal(monkeypatch):
    record = BatchJobRepository.save(BatchJobRecord(batch_job_id="batch_failed", limit=1))

    class FailedJob:
        @staticmethod
        def get_status():
            return "failed"

    monkeypatch.setattr(ProcessingQueueService, "_redis_connection", staticmethod(lambda: object()))
    monkeypatch.setattr("rq.job.Job.fetch", lambda *_args, **_kwargs: FailedJob())

    failed = BatchProcessingService.get_status(record.batch_job_id)

    assert failed is not None
    assert failed.state == "FAILED"
    assert failed.progress == 100
