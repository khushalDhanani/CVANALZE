from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile, BackgroundTasks

from app.core.config import settings
from app.core.logging import logger
from app.repositories.job import JobRepository
from app.repositories.result import ResultRepository
from app.repositories.training import TrainingRepository
from app.schemas.analysis import (
    EnrichedCandidateAnalysis,
    HRReviewRequest,
    TrainingExample,
)
from app.schemas.cv import CVMatchRequest, CVProcessingResponse
from app.services.cv_service import process_cv_file, get_stable_cv_key
from app.services.match_service import MatchService

router = APIRouter(prefix="/match", tags=["Matching"])


@router.get("/health")
async def check_llm_health():
    """Check if the local Ollama instance is reachable."""
    if not settings.LLM_ENABLED:
        return {"status": "disabled", "message": "LLM matching is disabled in config."}

    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            models = response.json().get("models", [])
            model_names = [m.get("name") for m in models]

            return {
                "status": "online",
                "model_configured": settings.OLLAMA_MODEL,
                "model_available": any(
                    settings.OLLAMA_MODEL in name for name in model_names
                ),
                "available_models": model_names,
            }
    except Exception as exc:  # noqa: BLE001
        return {"status": "offline", "error": str(exc)}


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


async def background_upload_and_analyze(filename: str, content: bytes, content_type: str | None):
    try:
        await process_cv_file(
            filename=filename,
            content=content,
            content_type=content_type,
        )
    except Exception as exc:
        logger.exception(f"Background match processing failed: {exc}")


@router.post("/upload", response_model=CVProcessingResponse)
async def upload_and_analyze(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...)  # noqa: B008
):
    """Upload CV, parse with Docling, and perform LLM-enriched semantic matching in background."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    try:
        content = await file.read()
        cv_key = get_stable_cv_key(file.filename)

        # Preserve raw upload file for re-run analysis
        try:
            settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
            raw_path = settings.UPLOADS_DIR / file.filename
            raw_path.write_bytes(content)
            logger.info(f"Saved raw upload file to '{raw_path}'.")
        except Exception as write_err:
            logger.warning(f"Failed writing upload file to UPLOADS_DIR: {write_err}")

        background_tasks.add_task(
            background_upload_and_analyze,
            filename=file.filename,
            content=content,
            content_type=file.content_type,
        )


        return CVProcessingResponse(
            message="10% - Upload and match processing started in the background...",
            cv_key=cv_key,
            status="processing",
            progress=10
        )

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(f"Failed to process CV upload: {exc}")
        raise HTTPException(
            status_code=500, detail="An internal error occurred while processing the CV."
        ) from exc


@router.get("/status/{cv_key}")
async def get_match_status(cv_key: str):
    """Get the status or result of an enriched background match job."""
    result = ResultRepository.read_result_by_filename(f"{cv_key}.json")
    if result:
        if result.get("status") == "FAILED":
            return CVProcessingResponse(
                message=result.get("message") or result.get("error") or "CV processing failed.",
                cv_key=cv_key,
                status="FAILED",
                progress=100,
                stage=result.get("stage"),
                failed_step=result.get("failed_step"),
                error_details=result.get("error_details"),
            )
        match_analysis = result.get("match_analysis")
        if match_analysis:
            match_analysis["scan_id"] = result.get("scan_id", result.get("id"))
            match_analysis["parsed_at"] = result.get("parsed_at", result.get("scanned_at"))
            try:
                return EnrichedCandidateAnalysis.model_validate(match_analysis)
            except Exception:
                return match_analysis
        
        return CVProcessingResponse(
            message=result.get("message") or f"{result.get('progress', 50)}% - Processing in progress...",
            cv_key=cv_key,
            status=result.get("status", "processing"),
            progress=result.get("progress", 50),
            stage=result.get("stage")
        )
        
    return CVProcessingResponse(
        message="Uploading and parsing CV...",
        cv_key=cv_key,
        status="processing",
        progress=25,
        stage="parsing"
    )


@router.post("/reanalyze/{scan_id}")
async def reanalyze_scan(scan_id: str):
    """Re-run LLM semantic matching on a previously parsed CV (by scan_id)."""
    matching_files = ResultRepository.find_results_by_scan_id(scan_id)

    # Filter out already enriched files
    original_files = [
        f for f in matching_files if not f.name.endswith("_enriched.json")
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
    enriched_files = [f for f in matching_files if f.name.endswith("_enriched.json")]
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
