from __future__ import annotations

import time

from app.core.profiler import PipelineProfiler
from app.core.rate_limit import InMemoryRateLimiter


def test_in_memory_rate_limiter_allows_and_throttles() -> None:
    limiter = InMemoryRateLimiter()
    identifier = "test-client-ip"

    # Allow requests up to limit
    for _ in range(5):
        decision = limiter.check(identifier, limit=5, window_seconds=60)
        assert decision.allowed is True

    # 6th request should exceed limit
    excess_decision = limiter.check(identifier, limit=5, window_seconds=60)
    assert excess_decision.allowed is False
    assert excess_decision.remaining == 0
    assert excess_decision.reset_after_seconds > 0


def test_in_memory_rate_limiter_reset() -> None:
    limiter = InMemoryRateLimiter()
    identifier = "test-client-ip"
    limiter.check(identifier, limit=1, window_seconds=60)

    # Exceeded
    assert limiter.check(identifier, limit=1, window_seconds=60).allowed is False

    # Reset
    limiter.reset()
    assert limiter.check(identifier, limit=1, window_seconds=60).allowed is True


def test_pipeline_profiler_time_stage() -> None:
    profiler = PipelineProfiler()
    with profiler.time_stage("docling_extraction"):
        time.sleep(0.01)

    with profiler.time_stage("prefilter"):
        time.sleep(0.01)

    profiler.record_cache_event(hit=True)
    metrics = profiler.finish()

    assert metrics.docling_extraction_ms > 0.0
    assert metrics.prefilter_ms > 0.0
    assert metrics.cache_hits == 1
    assert metrics.cache_hit is True
    assert metrics.total_execution_ms > 0.0
