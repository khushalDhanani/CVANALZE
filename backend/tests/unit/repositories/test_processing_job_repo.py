from __future__ import annotations

from app.core.cache import processing_job_cache_manager
from app.repositories.processing_job import ProcessingJobRepository
from app.schemas.contracts import JobState, ProcessingExecutionMode, ProcessingJobRecord


def test_build_job_id_deterministic() -> None:
    job_id_1 = ProcessingJobRepository.build_job_id("cv_key_101", "sha256_hash_101")
    job_id_2 = ProcessingJobRepository.build_job_id("cv_key_101", "sha256_hash_101")
    assert job_id_1 == job_id_2
    assert job_id_1.startswith("cvjob_")


def test_processing_job_cache_mirroring() -> None:
    record = ProcessingJobRecord(
        job_id="cvjob_test12345",
        cv_key="cv_key_test123",
        content_hash="content_sha256_test",
        filename="candidate.pdf",
        storage_filename="storage_candidate.pdf",
        parser_version="1.0.0",
        schema_version="1.0.0",
        state=JobState.QUEUED,
        progress=10,
        stage="QUEUED",
        message="Queued in test",
        execution_mode=ProcessingExecutionMode.RQ,
        attempt=0,
        max_attempts=3,
    )
    # Save into cache manager
    ProcessingJobRepository._save_cache(record)

    # Lookup by job_id
    found = ProcessingJobRepository.get("cvjob_test12345")
    assert found is not None
    assert found.job_id == "cvjob_test12345"
    assert found.cv_key == "cv_key_test123"
