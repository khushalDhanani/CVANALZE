from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.core.cv_identity import CVIdentityCollisionError, resolve_cv_identity
from app.core.logging import logger
from app.repositories.processing_job import ProcessingJobRepository
from app.repositories.result import ResultRepository
from app.schemas.analysis import EnrichedCandidateAnalysis
from app.schemas.cv import CVMatchRequest, CVProcessingResponse, CVUploadResponse
from app.schemas.match import CandidateMatchAnalysis
from app.services.processing_queue import (
    ProcessingQueueService,
    ProcessingQueueUnavailableError,
    run_processing_job_fallback,
)
from app.services.scoring_engine import ScoringEngine
from app.services.upload_service import UploadService, UploadValidationError

router = APIRouter(prefix="/cv", tags=["CV"])


def background_process_cv(job_id: str) -> None:
    run_processing_job_fallback(job_id)


@router.post("/upload", response_model=CVProcessingResponse)
async def upload_cv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),  # noqa: B008
    candidate_id: str | None = Form(None),
    cv_id: str | None = Form(None),
):
    try:
        normalized = UploadService.normalize_filename(file.filename)
        identity = resolve_cv_identity(normalized.safe_filename, candidate_id, cv_id)
        cv_key = identity.canonical_key
        accepted = await UploadService.accept_and_persist(file, storage_key=cv_key)
        try:
            ResultRepository.assert_identity_available(identity, accepted.content_hash)
            submission = ProcessingQueueService.submit_upload(
                cv_key=cv_key,
                content_hash=accepted.content_hash,
                filename=accepted.safe_filename,
                content_type=accepted.detected_content_type,
                candidate_id=candidate_id,
                cv_id=cv_id,
                storage_filename=accepted.storage_filename,
            )
            if submission.schedule_development_fallback:
                background_tasks.add_task(background_process_cv, submission.record.job_id)
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
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc
    except ProcessingQueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

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
        if result.get("status") == "processing" and not result.get("match_analysis"):
            payload = ProcessingQueueService.legacy_status_payload(job) if job else {}
            return CVProcessingResponse(
                message=f"{result.get('progress', 25)}% - {result.get('stage', 'Processing')}...",
                cv_key=result.get("id") or cv_key,
                status="processing",
                progress=result.get("progress", 25),
                stage=result.get("stage"),
                job_id=payload.get("job_id"),
                job_state=payload.get("job_state", "PROCESSING"),
                execution_mode=payload.get("execution_mode"),
                retry_count=payload.get("retry_count"),
            )
        if "scan_id" not in result and "id" in result:
            result["scan_id"] = result["id"]
        if "parsed_at" not in result and "scanned_at" in result:
            result["parsed_at"] = result["scanned_at"]
        result["status"] = "COMPLETED"
        result["progress"] = 100
        result["stage"] = "complete"
        if job:
            result.update(
                job_id=job.job_id,
                job_state=job.state.value,
                execution_mode=job.execution_mode.value,
                retry_count=job.attempt,
            )
        return CVUploadResponse(**result)

    if job:
        return CVProcessingResponse(**ProcessingQueueService.legacy_status_payload(job))
    if ProcessingQueueService.unknown_job_compatibility_active():
        return CVProcessingResponse(
            message="25% - CV is still processing or does not exist...",
            cv_key=cv_key,
            status="processing",
            progress=25,
            job_state="UNKNOWN",
        )
    raise HTTPException(status_code=404, detail=f"CV processing job '{cv_key}' was not found.")
