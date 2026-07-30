from fastapi import APIRouter, File, Form, HTTPException, UploadFile, BackgroundTasks

from app.core.config import settings
from app.core.logging import logger
from app.schemas.cv import CVMatchRequest, CVUploadResponse, CVProcessingResponse
from app.schemas.match import CandidateMatchAnalysis
from app.services.cv_service import process_cv_file, get_stable_cv_key
from app.repositories.result import ResultRepository
from app.services.scoring_engine import ScoringEngine

router = APIRouter(prefix="/cv", tags=["CV"])



async def background_process_cv(*args, **kwargs):
    try:
        await process_cv_file(*args, **kwargs)
    except Exception as exc:
        from app.core.logging import logger
        logger.exception(f"Background CV processing failed: {exc}")


@router.post("/upload", response_model=CVProcessingResponse)
async def upload_cv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),  # noqa: B008
    candidate_id: str | None = Form(None),
    cv_id: str | None = Form(None),
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required.",
        )

    from pathlib import Path
    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '.{ext}'. Allowed formats: docx, pdf.",
        )


    try:
        content = await file.read()
        cv_key = get_stable_cv_key(file.filename, candidate_id, cv_id)

        # Preserve raw upload file for re-run analysis
        try:
            settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
            raw_path = settings.UPLOADS_DIR / file.filename
            raw_path.write_bytes(content)
            logger.info(f"Saved raw upload file to '{raw_path}'.")
        except Exception as write_err:
            logger.warning(f"Failed writing upload file to UPLOADS_DIR: {write_err}")

        background_tasks.add_task(
            background_process_cv,
            filename=file.filename,
            content=content,
            content_type=file.content_type,
            candidate_id=candidate_id,
            cv_id=cv_id,
        )


        return CVProcessingResponse(
            message="10% - CV processing started in the background...",
            cv_key=cv_key,
            status="processing",
            progress=10
        )


    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(f"Failed to process CV: {exc}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while processing the CV.",
        ) from exc


@router.post("/match", response_model=CandidateMatchAnalysis)
async def match_cv_text(payload: CVMatchRequest):
    if not payload.cv_text or not payload.cv_text.strip():
        raise HTTPException(
            status_code=400,
            detail="CV text content cannot be empty.",
        )

    try:
        return ScoringEngine.analyze_cv(payload.cv_text)
    except Exception as exc:
        logger.exception(f"Failed to analyze CV text: {exc}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during CV analysis.",
        ) from exc


@router.get("/status/{cv_key}", response_model=CVUploadResponse | CVProcessingResponse)
async def get_cv_status(cv_key: str):
    """Get the status or result of a background CV processing job."""
    result = ResultRepository.read_result_by_filename(f"{cv_key}.json")
    if result:
        if result.get("status") == "FAILED":
            return CVProcessingResponse(
                message=result.get("message") or result.get("error") or "CV processing failed.",
                cv_key=cv_key,
                status="FAILED",
                progress=100,
            )
        if result.get("status") == "processing":
            return CVProcessingResponse(
                message=f"{result.get('progress', 25)}% - {result.get('stage', 'Processing')}...",
                cv_key=result.get("id") or cv_key,
                status="processing",
                progress=result.get("progress"),
                stage=result.get("stage")
            )
        if "scan_id" not in result and "id" in result:
            result["scan_id"] = result["id"]
        if "parsed_at" not in result and "scanned_at" in result:
            result["parsed_at"] = result["scanned_at"]
        return CVUploadResponse(**result)
    return CVProcessingResponse(
        message="25% - CV is still processing or does not exist...",
        cv_key=cv_key,
        status="processing",
        progress=25
    )
