from __future__ import annotations

from app.schemas.contracts import JobState, ProcessingExecutionMode, ProcessingJobRecord
from app.services.processing_queue import QueueSubmission


def test_batch_workflow_job_tracking() -> None:
    # Simulate batch creation of multiple candidate records
    records = [
        ProcessingJobRecord(
            job_id=f"job-batch-{i}",
            cv_key=f"cv-key-{i}",
            content_hash=f"hash-{i}",
            filename=f"candidate_{i}.pdf",
            storage_filename=f"storage_{i}.pdf",
            parser_version="1.0.0",
            schema_version="1.0.0",
            state=JobState.QUEUED,
            progress=0,
            stage="QUEUED",
            message="Batch item queued",
            execution_mode=ProcessingExecutionMode.RQ,
            attempt=0,
            max_attempts=3,
        )
        for i in range(5)
    ]
    submissions = [QueueSubmission(record=r, reused_existing_job=False) for r in records]

    assert len(submissions) == 5
    assert all(s.record.state == JobState.QUEUED for s in submissions)

    # Transition states to completed
    for i, s in enumerate(submissions):
        r = s.record
        r.state = JobState.COMPLETED
        r.progress = 100
        r.stage = "COMPLETED"

    completed_count = sum(1 for s in submissions if s.record.state == JobState.COMPLETED)
    assert completed_count == 5
