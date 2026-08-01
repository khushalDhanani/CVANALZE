import time

from app.core.profiler import PipelineProfiler
from app.schemas.job_context import JobEvaluationContext
from app.services.scoring_engine import ScoringEngine


def test_pipeline_profiler_stage_timing():
    profiler = PipelineProfiler()

    with profiler.time_stage("candidate_context"):
        time.sleep(0.01)

    with profiler.time_stage("vacancy_context"):
        time.sleep(0.01)

    metrics = profiler.finish()

    assert metrics.candidate_context_ms >= 5.0
    assert metrics.vacancy_context_ms >= 5.0
    assert metrics.total_execution_ms >= 10.0


def test_pipeline_profiler_cache_events_and_json():
    profiler = PipelineProfiler()

    profiler.record_cache_event(hit=True)
    profiler.record_cache_event(hit=True)
    profiler.record_cache_event(hit=False)

    data = profiler.to_dict()
    assert data["cache_hits"] == 2
    assert data["cache_misses"] == 1
    assert data["cache_hit"] is True

    json_str = profiler.to_json()
    assert '"cache_hits": 2' in json_str


def test_scoring_engine_profiler_integration():
    cv_text = """
    ## Software Developer
    Skills: Python, FastAPI, PostgreSQL
    Experience: 3 years
    """
    jobs = [
        {"id": "j1", "title": "Python Developer", "department_name": "CIS Team"},
        {"id": "j2", "title": "DevOps Engineer", "department_name": "CIS Team"},
    ]
    job_contexts = JobEvaluationContext.from_jobs(jobs)

    profiler = PipelineProfiler()
    analysis = ScoringEngine.analyze_cv(cv_text, job_openings=job_contexts, profiler=profiler)

    assert analysis.best_match is not None
    assert profiler.metrics.candidate_context_ms > 0.0
    assert profiler.metrics.vacancy_context_ms >= 0.0
    assert profiler.metrics.scoring_ms > 0.0
