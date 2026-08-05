import time
import hashlib
from typing import Optional

from app.schemas.work_experience_extraction import (
    WorkExperienceExtractionRequest,
    WorkExperienceExtractionResponse,
    WorkExperienceExtractionMetadata,
    CurrentEmployment,
    CurrentEmployer,
)
from app.services.llm_service import OllamaLLMService
from app.services.work_experience_post_processor import WorkExperiencePostProcessor
from app.services.work_experience_calculation_service import WorkExperienceCalculationService
from app.prompts.work_experience_extraction_v1 import (
    WORK_EXPERIENCE_PROMPT_VERSION,
    WORK_EXPERIENCE_EXTRACTION_PROMPT,
)
from app.core.config import settings
from app.services.ollama_transport import OllamaError


class WorkExperienceExtractionEngine:
    CALCULATION_VERSION = "1.0.0"

    @classmethod
    async def process(
        cls, request: WorkExperienceExtractionRequest
    ) -> WorkExperienceExtractionResponse:
        start_time = time.perf_counter()

        # Text truncation
        safe_text = request.ocr_text[: request.config.max_ocr_text_length] if hasattr(request.config, "max_ocr_text_length") else request.ocr_text[:100000]

        prompt = WORK_EXPERIENCE_EXTRACTION_PROMPT.format(
            candidate_id=request.candidate_id,
            ocr_text=safe_text,
        )

        # Cache key for raw extraction only
        text_hash = hashlib.sha256(safe_text.encode("utf-8")).hexdigest()
        cache_key = f"work-exp-extract:{text_hash}:{WORK_EXPERIENCE_PROMPT_VERSION}:{settings.OLLAMA_MODEL}"

        try:
            llm_result = await OllamaLLMService.extract_work_experience(
                prompt=prompt,
                prompt_version=WORK_EXPERIENCE_PROMPT_VERSION,
                cache_key=cache_key,
            )
        except OllamaError as exc:
            raise exc

        # Ensure we always get a valid result or it throws
        if not llm_result:
            raise ValueError("LLM generation returned an empty result")

        records, duplicates = WorkExperiencePostProcessor.process_records(
            llm_records=llm_result.employment_records,
            config=request.config,
            reference_date_str=request.reference_date,
        )

        summary = WorkExperienceCalculationService.calculate_experience(
            records=records, config=request.config
        )

        current_employers = []
        for r in records:
            if r.include_in_experience and r.is_current:
                current_employers.append(
                    CurrentEmployer(
                        record_id=r.record_id,
                        company_name=r.company_name_normalized or r.company_name_original,
                        job_title=r.job_title_normalized or r.job_title_original,
                        start_date=r.start_date_normalized,
                    )
                )

        current_employment = CurrentEmployment(
            is_currently_employed=len(current_employers) > 0,
            current_job_count=len(current_employers),
            current_employers=current_employers,
        )

        requires_review = any(r.requires_review for r in records) or llm_result.overall_confidence < request.config.human_review_threshold
        
        all_review_reasons = []
        for r in records:
            for rr in r.review_reason_codes:
                all_review_reasons.append(
                    {
                        "code": rr,
                        "record_id": r.record_id,
                        "message": f"Review required for {r.record_id} due to {rr}"
                    }
                )

        processing_time_ms = int((time.perf_counter() - start_time) * 1000)

        metadata = WorkExperienceExtractionMetadata(
            prompt_version=WORK_EXPERIENCE_PROMPT_VERSION,
            calculation_version=cls.CALCULATION_VERSION,
            llm_model=settings.OLLAMA_MODEL,
            cache_hit=False,  # This could be retrieved if profiler was exposed
            processing_time_ms=processing_time_ms,
        )

        return WorkExperienceExtractionResponse(
            candidate_id=request.candidate_id,
            reference_date=request.reference_date,
            extraction_status="success" if not requires_review else "partial",
            detected_date_pattern=llm_result.detected_date_pattern,
            current_employment=current_employment,
            experience_summary=summary,
            employment_records=records,
            duplicate_records=duplicates,
            unresolved_employment_text=llm_result.unresolved_employment_text,
            global_warnings=llm_result.global_warnings,
            review_reasons=all_review_reasons,
            overall_confidence=llm_result.overall_confidence,
            requires_human_review=requires_review,
            metadata=metadata,
        )
