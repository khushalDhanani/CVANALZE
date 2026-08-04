import asyncio
import hashlib
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.repositories.result import ResultRepository
from app.schemas.candidate_search import (
    CandidateSearchRequest,
    CandidateSearchResponse,
)
from app.services.candidate_search_service import CandidateSearchService

router = APIRouter(prefix="/candidates", tags=["Candidates"])


@router.post("/search", response_model=CandidateSearchResponse)
def search_candidates_post(request: CandidateSearchRequest) -> CandidateSearchResponse:
    """
    Enterprise Semantic Candidate Search endpoint.
    Converts natural language search query into embeddings, computes vector similarity,
    and applies structured deterministic filters (department, experience, location, skills, education, status).
    """
    try:
        return CandidateSearchService.search_candidates(request)
    except Exception as exc:
        from app.core.logging import logger

        logger.exception(f"Candidate search failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during candidate search.",
        ) from exc


@router.get("", response_model=list[dict[str, Any]])
def list_candidates(
    search: str | None = Query(None, description="Filter candidates by filename or keyword"),
    query: str | None = Query(None, description="Natural language semantic search query"),
    department: str | None = Query(None, description="Filter by department name"),
    min_experience: float | None = Query(None, description="Minimum total experience years"),
    max_experience: float | None = Query(None, description="Maximum total experience years"),
    location: str | None = Query(None, description="Filter by location name"),
    skills: list[str] | None = Query(None, description="List of required skills"),
    education: str | None = Query(None, description="Filter by education background"),
    status: str | None = Query(None, description="Filter candidate status"),
    min_similarity: float | None = Query(None, ge=0.0, le=1.0, description="Minimum vector similarity threshold"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    List all processed candidate results with summary match scores, vector similarity scores, and metadata.
    Supports natural language semantic search via query parameter.
    """
    try:
        search_query = query if query is not None else search
        req = CandidateSearchRequest(
            query=search_query,
            department=department,
            min_experience=min_experience,
            max_experience=max_experience,
            location=location,
            skills=skills,
            education=education,
            status=status,
            min_similarity=min_similarity,
            limit=limit,
        )
        res = CandidateSearchService.search_candidates(req)
        return [item.model_dump() for item in res.candidates]
    except Exception as exc:
        from app.core.logging import logger

        logger.exception(f"Candidate listing failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while listing candidates.",
        ) from exc


@router.get("/{candidate_id}", response_model=dict[str, Any])
def get_candidate_detail(candidate_id: str):
    """
    Retrieve complete parsed candidate result and full match analysis by candidate ID / scan key.
    """
    cid = candidate_id.strip()
    result = ResultRepository.resolve_result(cid)

    if not result:
        raise HTTPException(status_code=404, detail=f"Candidate record '{cid}' not found.")

    if "experience_years" not in result or result.get("experience_years") is None:
        from app.services.experience_calculator import ExperienceCalculator

        resume_json = result.get("resume_json") or {}
        cv_text = result.get("markdown") or result.get("text") or ""
        stem = str(result.get("id") or result.get("scan_id") or cid.removesuffix(".json"))
        canonical_exp = ExperienceCalculator.calculate_canonical_experience(resume_json, cv_text, candidate_id=stem)
        result["experience_years"] = canonical_exp["experience_years"]
        result["seniority"] = canonical_exp["seniority"]
        result["experience_summary"] = canonical_exp
        result["work_experience"] = canonical_exp["normalized_employment"]

    return result


@router.post("/{candidate_id}/reprocess", response_model=dict[str, Any])
async def reprocess_candidate(candidate_id: str, background_tasks: BackgroundTasks):
    """
    Invalidate and delete all existing cache entries related to candidate CV,
    preserve original CV file, and reprocess CV from scratch using latest pipeline.
    """
    from app.core.cache import CacheInvalidator, cv_result_cache_manager
    from app.core.config import settings
    from app.core.logging import logger
    from app.services.processing_queue import (
        ProcessingQueueService,
        ProcessingQueueUnavailableError,
        run_processing_job_fallback,
    )
    from app.services.upload_service import UploadService, UploadValidationError

    cid = candidate_id.strip()
    requested_key = cid.removesuffix(".json")
    existing_result = ResultRepository.resolve_result(requested_key)

    if not existing_result:
        raise HTTPException(status_code=404, detail=f"Candidate record '{requested_key}' not found.")

    cv_key = str(existing_result.get("id") or existing_result.get("scan_id") or requested_key)
    result_filename = f"{cv_key}.json"

    # Prevent duplicate concurrent reprocessing jobs
    if existing_result.get("status") == "processing":
        return {
            "message": existing_result.get("message") or "Analysis is already in progress for this candidate.",
            "cv_key": cv_key,
            "status": "processing",
            "progress": existing_result.get("progress", 20),
        }

    filename = existing_result.get("filename") or f"{cv_key}.pdf"
    cv_hash = existing_result.get("cv_hash")

    # Resolve and validate retained source bytes before altering the current result or caches.
    try:
        retained_upload = await asyncio.to_thread(
            UploadService.load_reprocessable_upload,
            storage_filename=existing_result.get("storage_filename"),
            original_filename=filename,
            cv_key=cv_key,
        )
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"The retained source CV is no longer valid for reprocessing: {exc}",
        ) from exc
    if retained_upload is None:
        raise HTTPException(
            status_code=409,
            detail="The retained source CV is unavailable; the existing result was preserved and cannot be reprocessed.",
        )

    filename = retained_upload.safe_filename
    content_type = retained_upload.detected_content_type
    raw_bytes = retained_upload.content

    # Invalidate and delete all cache entries for this CV
    cv_result_cache_manager.delete(result_filename)
    cv_result_cache_manager.delete_by_pattern(f"*{cv_key}*")
    if cv_hash:
        CacheInvalidator.invalidate_cv(cv_hash)

    # Unlink old result file on disk to ensure fresh reprocessing
    disk_path = settings.RESULTS_DIR / result_filename
    if disk_path.exists():
        try:
            disk_path.unlink()
        except Exception as e:
            logger.warning(f"Could not remove old result file '{disk_path}': {e}")

    # Save active processing marker
    processing_marker = {
        "id": cv_key,
        "scan_id": cv_key,
        "filename": filename,
        "storage_filename": retained_upload.storage_filename,
        "candidate_id": existing_result.get("candidate_id"),
        "cv_id": existing_result.get("cv_id"),
        "cv_hash": cv_hash,
        "identity": existing_result.get("identity"),
        "legacy_cv_keys": existing_result.get("legacy_cv_keys") or [],
        "status": "processing",
        "message": "10% - Caches purged. Reprocessing CV from scratch...",
        "progress": 10,
        "created_at": existing_result.get("created_at"),
        "parsed_at": existing_result.get("parsed_at"),
    }
    ResultRepository.save_result(result_filename, processing_marker)

    try:
        submission = ProcessingQueueService.submit_upload(
            cv_key=cv_key,
            content_hash=hashlib.sha256(raw_bytes).hexdigest(),
            filename=filename,
            content_type=content_type,
            force_reprocess=True,
            candidate_id=existing_result.get("candidate_id"),
            cv_id=existing_result.get("cv_id"),
            storage_filename=retained_upload.storage_filename,
        )
    except ProcessingQueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if submission.schedule_development_fallback:
        background_tasks.add_task(run_processing_job_fallback, submission.record.job_id)

    return {
        "message": submission.record.message,
        "cv_key": cv_key,
        "status": "processing",
        "progress": submission.record.progress,
        "job_id": submission.record.job_id,
        "job_state": submission.record.state.value,
        "execution_mode": submission.record.execution_mode.value,
        "retry_count": submission.record.attempt,
    }
