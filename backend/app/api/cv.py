from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.core.logging import logger
from app.repositories.result import ResultRepository
from app.schemas.analysis import EnrichedCandidateAnalysis
from app.schemas.cv import CVMatchRequest, CVProcessingResponse, CVUploadResponse
from app.schemas.match import CandidateMatchAnalysis
from app.services.cv_service import get_stable_cv_key, process_cv_file
from app.services.scoring_engine import ScoringEngine
from app.services.upload_service import UploadService, UploadValidationError

router = APIRouter(prefix="/cv", tags=["CV"])



async def background_process_cv(*args, **kwargs):
    try:
        await process_cv_file(*args, **kwargs)
    except Exception as exc:
        from app.core.logging import logger
        UploadService.cleanup_after_processing(kwargs.get("storage_filename"), succeeded=False)
        logger.exception(f"Background CV processing failed: {exc}")


@router.post("/upload", response_model=CVProcessingResponse)
async def upload_cv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),  # noqa: B008
    candidate_id: str | None = Form(None),
    cv_id: str | None = Form(None),
):
    try:
        normalized = UploadService.normalize_filename(file.filename)
        cv_key = get_stable_cv_key(normalized.safe_filename, candidate_id, cv_id)
        accepted = await UploadService.accept_and_persist(file, storage_key=cv_key)
        try:
            background_tasks.add_task(
                background_process_cv,
                filename=accepted.safe_filename,
                content=accepted.content,
                content_type=accepted.detected_content_type,
                candidate_id=candidate_id,
                cv_id=cv_id,
                storage_filename=accepted.storage_filename,
            )
        except Exception:
            UploadService.remove_stored_upload(accepted.storage_filename)
            raise

        return CVProcessingResponse(
            message="10% - CV processing started in the background...",
            cv_key=cv_key,
            status="processing",
            progress=10
        )
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(f"Failed to process CV: {exc}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while processing the CV.",
        ) from exc


@router.post("/match", response_model=EnrichedCandidateAnalysis | CandidateMatchAnalysis)
async def match_cv_text(payload: CVMatchRequest):
    if not payload.cv_text or not payload.cv_text.strip():
        raise HTTPException(
            status_code=400,
            detail="CV text content cannot be empty.",
        )

    try:
        from app.services.match_service import MatchService
        return await MatchService.analyze_single_cv(payload.cv_text)
    except Exception as exc:
        logger.exception(f"Failed to analyze CV text: {exc}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during CV analysis.",
        ) from exc


@router.get("/status/{cv_key}", response_model=CVUploadResponse | CVProcessingResponse)
async def get_cv_status(cv_key: str):
    """Get the status or result of a background CV processing job."""
    result = ResultRepository.resolve_result(cv_key)
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
        if result.get("status") == "processing" and not result.get("match_analysis"):
            return CVProcessingResponse(
                message=f"{result.get('progress', 25)}% - {result.get('stage', 'Processing')}...",
                cv_key=result.get("id") or cv_key,
                status="processing",
                progress=result.get("progress", 25),
                stage=result.get("stage")
            )
        if "scan_id" not in result and "id" in result:
            result["scan_id"] = result["id"]
        if "parsed_at" not in result and "scanned_at" in result:
            result["parsed_at"] = result["scanned_at"]
        result["status"] = "COMPLETED"
        result["progress"] = 100
        result["stage"] = "complete"
        return CVUploadResponse(**result)

    return CVProcessingResponse(
        message="25% - CV is still processing or does not exist...",
        cv_key=cv_key,
        status="processing",
        progress=25
    )
