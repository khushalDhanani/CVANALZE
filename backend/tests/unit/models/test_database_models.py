from __future__ import annotations

from app.models.processing_job import CVProcessingJob
from app.models.result import CVResult


def test_cv_result_model_columns() -> None:
    assert CVResult.__tablename__ == "cv_results"
    assert hasattr(CVResult, "cv_key")
    assert hasattr(CVResult, "status")
    assert hasattr(CVResult, "full_name")
    assert hasattr(CVResult, "cv_hash")
    assert hasattr(CVResult, "resume_json")
    assert hasattr(CVResult, "match_analysis")


def test_cv_processing_job_model_columns() -> None:
    assert CVProcessingJob.__tablename__ == "cv_processing_jobs"
    assert hasattr(CVProcessingJob, "job_id")
    assert hasattr(CVProcessingJob, "cv_key")
    assert hasattr(CVProcessingJob, "state")
    assert hasattr(CVProcessingJob, "progress")
    assert hasattr(CVProcessingJob, "stage")
