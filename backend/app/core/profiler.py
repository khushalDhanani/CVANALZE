import time
from contextlib import contextmanager
from typing import Generator

from app.core.logging import logger
from app.schemas.analysis import PipelineStageMetrics


class PipelineProfiler:
    """
    Timer and metrics collector for profiling every stage of the CV matching pipeline.
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
            if hasattr(self.metrics, f"{stage_name}_ms"):
                setattr(self.metrics, f"{stage_name}_ms", duration_ms)

    def finish(self) -> PipelineStageMetrics:
        self.metrics.total_execution_ms = round((time.perf_counter() - self._start_time) * 1000.0, 2)
        if self.metrics.average_cv_processing_ms == 0.0:
            self.metrics.average_cv_processing_ms = self.metrics.total_execution_ms
        return self.metrics

    def log_summary(self) -> None:
        m = self.metrics
        llm_time_ms = m.ollama_request_ms + m.model_inference_ms
        cache_str = "HIT" if m.cache_hit else "MISS"
        logger.info(
            f"=== LLM Pipeline Execution Profile ==="
        )
        logger.info(
            f"Stage Timings (ms): JSON Loading={m.json_loading_ms}ms | Vacancy Retrieval={m.vacancy_retrieval_ms}ms | "
            f"Python Pre-filter={m.prefilter_ms}ms | Prompt Construction={m.prompt_construction_ms}ms | "
            f"Ollama Request={m.ollama_request_ms}ms | Model Inference={m.model_inference_ms}ms | "
            f"JSON Validation={m.json_validation_ms}ms | Scoring={m.scoring_ms}ms | Total Execution={m.total_execution_ms}ms"
        )
        logger.info(
            f"Pipeline Stats: LLM Time={llm_time_ms}ms | Tokens={m.token_count} ({m.context_char_count} chars) | "
            f"Vacancies Before Filter={m.vacancies_before_filtering} | Vacancies After Filter={m.vacancies_after_filtering} | "
            f"Cache Status={cache_str} | Avg Time per CV={m.average_cv_processing_ms}ms"
        )
