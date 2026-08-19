from __future__ import annotations

from app.schemas.contracts import JobState, ProcessingExecutionMode, ProcessingJobRecord
from app.services.processing_queue import QueueSubmission


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
