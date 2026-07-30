from typing import Any
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.schemas.candidate_search import (
    CandidateSearchRequest,
    CandidateSearchResponse,
)
from app.services.candidate_search_service import CandidateSearchService
from app.repositories.result import ResultRepository


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
        raise HTTPException(status_code=500, detail="An internal error occurred during candidate search.") from exc


@router.get("", response_model=list[dict[str, Any]])
def list_candidates(
    search: str | None = Query(None, description="Filter candidates by filename or keyword"),
    query: str | None = Query(None, description="Natural language semantic search query"),
    department: str | None = Query(None, description="Filter by department name"),
    min_experience: float | None = Query(None, description="Minimum total experience years"),
    max_experience: float | None = Query(None, description="Maximum total experience years"),
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
            limit=limit,
        )
        res = CandidateSearchService.search_candidates(req)
        return [item.model_dump() for item in res.candidates]
    except Exception as exc:
        from app.core.logging import logger
        logger.exception(f"Candidate listing failed: {exc}")
        raise HTTPException(status_code=500, detail="An internal error occurred while listing candidates.") from exc


@router.get("/{candidate_id}", response_model=dict[str, Any])
def get_candidate_detail(candidate_id: str):
    """
    Retrieve complete parsed candidate result and full match analysis by candidate ID / scan key.
    """
    cid = candidate_id.strip()
    filename = f"{cid}.json" if not cid.endswith(".json") else cid
    result = ResultRepository.read_result_by_filename(filename)
    
    if not result:
        # Fallback search by scan_id / stem
        stem = cid[:-5] if cid.endswith(".json") else cid
        matches = ResultRepository.find_results_by_scan_id(stem)
        if matches:
            first_match = matches[0]
            result = ResultRepository.read_result(first_match)

    if not result:
        raise HTTPException(status_code=404, detail=f"Candidate record '{cid}' not found.")

    if "similar_candidates" not in result or result.get("similar_candidates") is None:
        from app.services.similar_candidate_service import SimilarCandidateService
        from app.services.embedding_service import get_candidate_embedding
        stem = cid[:-5] if cid.endswith(".json") else cid
        cand_emb = get_candidate_embedding(stem)
        if cand_emb:
            result["similar_candidates"] = SimilarCandidateService.detect_similar_candidates(stem, cand_emb)
        else:
            result["similar_candidates"] = []

    return result


@router.post("/{candidate_id}/reprocess", response_model=dict[str, Any])
async def reprocess_candidate(candidate_id: str, background_tasks: BackgroundTasks):
    """
    Invalidate and delete all existing cache entries related to candidate CV,
    preserve original CV file, and reprocess CV from scratch using latest pipeline.
    """
    from app.core.config import settings
    from app.core.cache import (
        cv_result_cache_manager,
        doc_cache_manager,
        llm_cache_manager,
        embedding_cache_manager,
        match_result_cache_manager,
    )
    from app.core.logging import logger
    from app.services.cv_service import process_cv_file

    cid = candidate_id.strip()
    result_filename = f"{cid}.json" if not cid.endswith(".json") else cid
    cv_key = result_filename[:-5] if result_filename.endswith(".json") else result_filename
    
    existing_result = ResultRepository.read_result_by_filename(result_filename)
    if not existing_result:
        matches = ResultRepository.find_results_by_scan_id(cv_key)
        if matches:
            existing_result = ResultRepository.read_result(matches[0])

    if not existing_result:
        raise HTTPException(status_code=404, detail=f"Candidate record '{cv_key}' not found.")


    # Prevent duplicate concurrent reprocessing jobs
    if existing_result.get("status") == "processing":
        return {
            "message": existing_result.get("message") or "Analysis is already in progress for this candidate.",
            "cv_key": cv_key,
            "status": "processing",
            "progress": existing_result.get("progress", 20),
        }

    filename = existing_result.get("filename") or f"{cv_key}.pdf"
    content_type = existing_result.get("content_type")
    cv_hash = existing_result.get("cv_hash")

    # Invalidate and delete all cache entries for this CV
    cv_result_cache_manager.delete(result_filename)
    cv_result_cache_manager.delete_by_pattern(f"*{cv_key}*")
    if cv_hash:
        doc_cache_manager.delete(cv_hash)
        doc_cache_manager.delete_by_pattern(f"*{cv_hash}*")
        llm_cache_manager.delete_by_pattern(f"*{cv_hash}*")
        embedding_cache_manager.delete_by_pattern(f"*{cv_hash}*")
        match_result_cache_manager.delete_by_pattern(f"*{cv_hash}*")

    # Unlink old result file on disk to ensure fresh reprocessing
    disk_path = settings.RESULTS_DIR / result_filename
    if disk_path.exists():
        try:
            disk_path.unlink()
        except Exception as e:
            logger.warning(f"Could not remove old result file '{disk_path}': {e}")

    # Locate raw file content from UPLOADS_DIR or fallback to extracted text
    raw_bytes = None
    raw_file_candidates = [
        settings.UPLOADS_DIR / filename,
        settings.UPLOADS_DIR / f"{cv_key}.pdf",
        settings.UPLOADS_DIR / f"{cv_key}.docx",
    ]
    for path in raw_file_candidates:
        if path.exists() and path.is_file():
            try:
                raw_bytes = path.read_bytes()
                logger.info(f"[REPROCESS] Found preserved raw file at '{path}'.")
                break
            except Exception as e:
                logger.warning(f"Failed reading raw upload file '{path}': {e}")

    if not raw_bytes:
        fallback_text = existing_result.get("markdown") or existing_result.get("text") or ""
        if fallback_text:
            try:
                import fitz
                doc = fitz.open()
                page = doc.new_page()
                page.insert_text((50, 50), fallback_text[:3000])
                raw_bytes = doc.tobytes()
                doc.close()
                filename = f"{cv_key}.pdf"
                content_type = "application/pdf"
                logger.info(f"[REPROCESS] Created synthetic PDF from extracted text for candidate '{cv_key}'.")
            except Exception as pdf_err:
                logger.warning(f"Failed generating synthetic PDF from text: {pdf_err}")
                raw_bytes = fallback_text.encode("utf-8")
                filename = f"{cv_key}.pdf"
                content_type = "application/pdf"



    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Original CV content is missing and cannot be reprocessed.")

    # Save active processing marker
    processing_marker = {
        "id": cv_key,
        "scan_id": cv_key,
        "filename": filename,
        "status": "processing",
        "message": "10% - Caches purged. Reprocessing CV from scratch...",
        "progress": 10,
        "created_at": existing_result.get("created_at"),
        "parsed_at": existing_result.get("parsed_at"),
    }
    ResultRepository.save_result(result_filename, processing_marker)

    background_tasks.add_task(
        process_cv_file,
        filename=filename,
        content=raw_bytes,
        content_type=content_type,
        force_reprocess=True,
        candidate_id=existing_result.get("candidate_id"),
        cv_id=existing_result.get("cv_id"),
    )

    return {
        "message": "10% - Caches purged. Reprocessing CV from scratch...",
        "cv_key": cv_key,
        "status": "processing",
        "progress": 10,
    }

