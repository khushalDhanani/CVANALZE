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
            f"=== 8-Stage CV Pipeline Execution Profile ==="
        )
        logger.info(
            f"1. Upload & Read={m.upload_ms}ms | 2. Docling Extraction={m.docling_extraction_ms}ms | "
            f"3. Resume JSON={m.resume_json_ms}ms | 4. DB Vacancy Retrieval={m.vacancy_retrieval_ms}ms | "
            f"5. Cache Check={m.cache_lookup_ms}ms | 6. Python Pre-filter={m.prefilter_ms}ms | "
            f"7. LLM Request/Inference={llm_time_ms}ms (req: {m.ollama_request_ms}ms, inf: {m.model_inference_ms}ms, val: {m.json_validation_ms}ms) | "
            f"8. Scoring & Matching={m.scoring_ms}ms | Total Execution={m.total_execution_ms}ms"
        )
        logger.info(
            f"Pipeline Metrics: LLM Tokens={m.token_count} ({m.context_char_count} chars) | "
            f"Vacancies Pre-filter={m.vacancies_before_filtering} -> Post-filter={m.vacancies_after_filtering} | "
            f"Cache Status={cache_str} | Total CV Processing Time={m.total_execution_ms}ms"
        )
