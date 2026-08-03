from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.core.config import settings
from app.core.cv_identity import CVIdentityCollisionError, resolve_cv_identity
from app.core.logging import logger
from app.repositories.job import JobRepository
from app.repositories.processing_job import ProcessingJobRepository
from app.repositories.result import ResultRepository
from app.repositories.training import TrainingRepository
from app.schemas.analysis import (
    EnrichedCandidateAnalysis,
    HRReviewRequest,
    TrainingExample,
)
from app.schemas.cv import CVMatchRequest, CVProcessingResponse
from app.services.match_service import MatchService
from app.services.processing_queue import (
    ProcessingQueueService,
    ProcessingQueueUnavailableError,
    run_processing_job_fallback,
)
from app.services.upload_service import UploadService, UploadValidationError

router = APIRouter(prefix="/match", tags=["Matching"])


@router.get("/health")
async def check_llm_health():
    """Check if the local Ollama instance is reachable."""
    if not settings.LLM_ENABLED:
        return {"status": "disabled", "message": "LLM matching is disabled in config."}

    from app.services.llm_service import OllamaLLMService
    try:
        model_names = OllamaLLMService.get_available_models()
        is_healthy = bool(model_names) or OllamaLLMService.check_health()
        if is_healthy or model_names:
            return {
                "status": "online",
                "model_configured": settings.OLLAMA_MODEL,
                "model_available": any(
                    settings.OLLAMA_MODEL in name for name in model_names
                ),
                "available_models": model_names,
            }
        return {"status": "offline", "error": "Ollama server unreachable"}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Ollama health check failed: {type(exc).__name__}")
        return {"status": "offline", "error": "Ollama server unreachable"}



@router.post("/analyze", response_model=EnrichedCandidateAnalysis)
async def analyze_cv_text(payload: CVMatchRequest):
    """Analyze raw CV text using semantic LLM enrichment."""
    if not payload.cv_text or not payload.cv_text.strip():
        raise HTTPException(status_code=400, detail="CV text content cannot be empty.")

    try:
        return await MatchService.analyze_single_cv(payload.cv_text)
    except Exception as exc:
        logger.exception(f"Failed to analyze CV text: {exc}")
        raise HTTPException(
            status_code=500, detail="An internal error occurred during CV analysis."
        ) from exc


def background_upload_and_analyze(job_id: str) -> None:
    run_processing_job_fallback(job_id)


@router.post("/upload", response_model=CVProcessingResponse)
async def upload_and_analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)  # noqa: B008
):
    """Upload CV, parse with Docling, and perform LLM-enriched semantic matching in background."""
    try:
        normalized = UploadService.normalize_filename(file.filename)
        identity = resolve_cv_identity(normalized.safe_filename)
        cv_key = identity.canonical_key
        accepted = await UploadService.accept_and_persist(file, storage_key=cv_key)
        try:
            ResultRepository.assert_identity_available(identity, accepted.content_hash)
            submission = ProcessingQueueService.submit_upload(
                cv_key=cv_key,
                content_hash=accepted.content_hash,
                filename=accepted.safe_filename,
                content_type=accepted.detected_content_type,
                storage_filename=accepted.storage_filename,
            )
            if submission.schedule_development_fallback:
                background_tasks.add_task(background_upload_and_analyze, submission.record.job_id)
        except Exception:
            if not accepted.was_already_stored:
                UploadService.remove_stored_upload(accepted.storage_filename)
            raise

        return CVProcessingResponse(
            message=submission.record.message,
            cv_key=cv_key,
            status="processing",
            progress=submission.record.progress,
            stage=submission.record.stage,
            job_id=submission.record.job_id,
            job_state=submission.record.state.value,
            execution_mode=submission.record.execution_mode.value,
            retry_count=submission.record.attempt,
        )

    except CVIdentityCollisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except UploadValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ProcessingQueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(f"Failed to process CV upload: {exc}")
        raise HTTPException(
            status_code=500, detail="An internal error occurred while processing the CV."
        ) from exc


@router.get("/status/{cv_key}")
async def get_match_status(cv_key: str):
    """Get the status or result of an enriched background match job."""
    result = ResultRepository.resolve_result(cv_key)
    job = ProcessingJobRepository.get_by_cv_key(cv_key)
    if result:
        if result.get("status") == "FAILED":
            if job and job.state.value in ("QUEUED", "PROCESSING", "RETRYING"):
                return CVProcessingResponse(**ProcessingQueueService.legacy_status_payload(job))
            return CVProcessingResponse(
                message=result.get("message") or result.get("error") or "CV processing failed.",
                cv_key=cv_key,
                status="FAILED",
                progress=100,
                stage=result.get("stage"),
                failed_step=result.get("failed_step"),
                error_details=None,
                job_id=job.job_id if job else None,
                job_state=job.state.value if job else "FAILED",
                execution_mode=job.execution_mode.value if job else None,
                retry_count=job.attempt if job else None,
            )

        is_completed = (
            result.get("status") in ("COMPLETED", "NEW_CV", "REPROCESSED")
            or result.get("progress") == 100
            or result.get("is_complete") is True
        )

        match_analysis = result.get("match_analysis")
        if match_analysis:
            match_analysis["scan_id"] = result.get("scan_id", result.get("id"))
            match_analysis["parsed_at"] = result.get("parsed_at", result.get("scanned_at"))
            match_analysis["status"] = result.get("status", "COMPLETED")
            match_analysis["progress"] = result.get("progress", 100)
            match_analysis["stage"] = result.get("stage", "complete")
            match_analysis["is_complete"] = result.get("is_complete", True)
            if job:
                match_analysis.update(
                    job_id=job.job_id,
                    job_state=job.state.value,
                    execution_mode=job.execution_mode.value,
                    retry_count=job.attempt,
                )
            try:
                return EnrichedCandidateAnalysis.model_validate(match_analysis)
            except Exception:
                return match_analysis

        if is_completed:
            return CVProcessingResponse(
                message=result.get("message") or "100% - CV parsing & job matching complete!",
                cv_key=result.get("scan_id") or result.get("id") or cv_key,
                status="COMPLETED",
                progress=100,
                stage="complete",
                job_id=job.job_id if job else None,
                job_state=job.state.value if job else "COMPLETED",
                execution_mode=job.execution_mode.value if job else None,
                retry_count=job.attempt if job else None,
            )

        return CVProcessingResponse(
            message=result.get("message") or f"{result.get('progress', 50)}% - Processing in progress...",
            cv_key=cv_key,
            status=result.get("status", "processing"),
            progress=result.get("progress", 50),
            stage=result.get("stage"),
            job_id=job.job_id if job else None,
            job_state=job.state.value if job else "PROCESSING",
            execution_mode=job.execution_mode.value if job else None,
            retry_count=job.attempt if job else None,
        )

    if job:
        return CVProcessingResponse(**ProcessingQueueService.legacy_status_payload(job))
    if ProcessingQueueService.unknown_job_compatibility_active():
        return CVProcessingResponse(
            message="Uploading and parsing CV...",
            cv_key=cv_key,
            status="processing",
            progress=25,
            stage="parsing",
            job_state="UNKNOWN",
        )
    raise HTTPException(status_code=404, detail=f"CV processing job '{cv_key}' was not found.")


@router.post("/reanalyze/{scan_id}")
async def reanalyze_scan(scan_id: str):
    """Re-run LLM semantic matching on a previously parsed CV (by scan_id)."""
    matching_files = ResultRepository.find_results_by_scan_id(scan_id)

    # Filter out already enriched files
    original_files = [
        f for f in matching_files if not str(f).endswith("_enriched.json")
    ]

    if not original_files:
        raise HTTPException(
            status_code=404, detail=f"No original result found for scan_id: {scan_id}"
        )

    file_path = original_files[0]

    try:
        return await MatchService.analyze_from_result_file(file_path)
    except Exception as exc:
        logger.exception(f"Failed to reanalyze CV: {exc}")
        raise HTTPException(
            status_code=500, detail="An internal error occurred during reanalysis."
        ) from exc


@router.post("/hr-review")
async def submit_hr_review(payload: HRReviewRequest):
    """Submit HR corrections/approvals for a match to build training data."""
    matching_files = ResultRepository.find_results_by_scan_id(payload.scan_id)

    if not matching_files:
        raise HTTPException(
            status_code=404, detail=f"No result found for scan_id: {payload.scan_id}"
        )

    # Prefer enriched result if available
    enriched_files = [f for f in matching_files if str(f).endswith("_enriched.json")]
    file_path = enriched_files[0] if enriched_files else matching_files[0]

    try:
        data = ResultRepository.read_result(file_path)

        cv_text = data.get("markdown", "")

        # Get original analysis
        match_analysis = data.get("enriched_match_analysis") or data.get(
            "match_analysis"
        )
        if not match_analysis:
            raise HTTPException(
                status_code=400, detail="Result file lacks match_analysis."
            )

        suitable_openings = match_analysis.get("suitable_openings", [])
        job_eval = next(
            (j for j in suitable_openings if j.get("job_id") == payload.job_id), None
        )

        if not job_eval:
            raise HTTPException(
                status_code=404,
                detail=f"Job ID {payload.job_id} not found in analysis.",
            )

        from fastapi.concurrency import run_in_threadpool
        # Get Job Requirements
        job_req = await run_in_threadpool(JobRepository.get_job_by_id, payload.job_id) or {}

        # Extract original LLM reason and inferred skills if available
        original_llm = {
            "llm_reason": job_eval.get("llm_reason", ""),
            "inferred_skills": job_eval.get("inferred_skills", []),
        }

        example = TrainingExample(
            scan_id=payload.scan_id,
            job_id=payload.job_id,
            cv_text=cv_text,
            job_requirements=job_req,
            original_llm_analysis=original_llm,
            original_score=job_eval.get("score", 0.0),
            original_classification=job_eval.get("classification", "LOW"),
            hr_corrected_score=payload.corrected_score,
            hr_corrected_classification=payload.corrected_classification,
            hr_feedback=payload.feedback_notes,
            timestamp=datetime.now(UTC).isoformat(),
        )

        TrainingRepository.append_training_example(example)
        return {"status": "success", "message": "Training example saved."}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to save HR review: {exc}")
        raise HTTPException(
            status_code=500, detail="An internal error occurred while saving the HR review."
        ) from exc


@router.get("/training-data")
async def get_training_data(limit: int = 100):
    """Retrieve collected training examples for inspection."""
    examples = TrainingRepository.load_examples(limit=limit)
    return {"count": len(examples), "examples": examples}
