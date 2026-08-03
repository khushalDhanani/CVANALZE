import json
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from app.core.logging import logger
from app.schemas.analysis import PipelineStageMetrics


class PipelineProfiler:
    """
    Timer and metrics collector for profiling every stage of the CV matching pipeline.
    Supports single-stage timing contextmanagers, accumulated multi-vacancy stage timings,
    and structured telemetry logging.
    """

    def __init__(self) -> None:
        self.metrics = PipelineStageMetrics()
        self._start_time = time.perf_counter()

    @contextmanager
    def time_stage(self, stage_name: str) -> Generator[None, None, None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            attr = f"{stage_name}_ms"
            if hasattr(self.metrics, attr):
                current_val = getattr(self.metrics, attr, 0.0) or 0.0
                setattr(self.metrics, attr, round(current_val + duration_ms, 2))

    def add_stage_time(self, stage_name: str, duration_ms: float) -> None:
        attr = f"{stage_name}_ms"
        if hasattr(self.metrics, attr):
            current_val = getattr(self.metrics, attr, 0.0) or 0.0
            setattr(self.metrics, attr, round(current_val + duration_ms, 2))

    def record_cache_event(self, hit: bool) -> None:
        if hit:
            self.metrics.cache_hits += 1
            self.metrics.cache_hit = True
        else:
            self.metrics.cache_misses += 1

    def finish(self) -> PipelineStageMetrics:
        self.metrics.total_execution_ms = round((time.perf_counter() - self._start_time) * 1000.0, 2)
        if self.metrics.average_cv_processing_ms == 0.0:
            self.metrics.average_cv_processing_ms = self.metrics.total_execution_ms
        return self.metrics

    def to_dict(self) -> dict[str, Any]:
        return self.metrics.model_dump()

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def log_summary(self) -> None:
        m = self.finish()
        llm_time_ms = m.ollama_request_ms + m.model_inference_ms
        cache_str = f"HITS={m.cache_hits}, MISSES={m.cache_misses}"
        logger.info("=== CV Analysis & Matching Pipeline Profile ===")
        logger.info(
            f"[TIMINGS_MS] Docling={m.docling_extraction_ms} | Prefilter={m.prefilter_ms} | "
            f"CandContext={m.candidate_context_ms} | VacContext={m.vacancy_context_ms} | "
            f"ScoringTotal={m.scoring_ms} (Req:{m.evaluator_requirement_ms}, Trans:{m.evaluator_transition_ms}, "
            f"Comp:{m.evaluator_component_ms}, Guard:{m.evaluator_cross_domain_ms}, Rec:{m.evaluator_recommendation_ms}) | "
            f"LLM={llm_time_ms} | Total={m.total_execution_ms}"
        )
        logger.info(f"[TELEMETRY] Vacancies: Raw={m.vacancies_before_filtering} -> Filtered={m.vacancies_after_filtering} | Cache: {cache_str} | Total Time={m.total_execution_ms}ms")
