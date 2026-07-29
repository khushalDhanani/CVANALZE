from typing import Any
from fastapi import APIRouter, HTTPException, Query

from app.repositories.result import ResultRepository

router = APIRouter(prefix="/candidates", tags=["Candidates"])


@router.get("", response_model=list[dict[str, Any]])
def list_candidates(
    search: str | None = Query(None, description="Filter candidates by filename or keyword"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    List all processed candidate results with summary match scores and metadata.
    """
    results = ResultRepository.list_all_results()
    
    if search:
        s_lower = search.lower()
        filtered = []
        for r in results:
            fname = r.get("filename", "").lower()
            cv_id = r.get("id", "").lower()
            text = r.get("markdown", "")[:500].lower()
            if s_lower in fname or s_lower in cv_id or s_lower in text:
                filtered.append(r)
        results = filtered

    summaries = []
    for r in results[:limit]:
        match_analysis = r.get("match_analysis", {})
        best_match = match_analysis.get("best_match", {})
        
        summaries.append({
            "id": r.get("id"),
            "filename": r.get("filename"),
            "parsed_at": r.get("parsed_at") or r.get("created_at"),
            "page_count": r.get("page_count", 1),
            "is_scanned": r.get("is_scanned", False),
            "ocr_applied": r.get("ocr_applied", False),
            "primary_department": match_analysis.get("primary_department"),
            "best_match": {
                "job_title": best_match.get("job_title"),
                "department": best_match.get("department") or best_match.get("department_name"),
                "score": best_match.get("score") or best_match.get("overall_score"),
                "classification": best_match.get("classification"),
                "recommendation": best_match.get("recommendation"),
            },
        })

    return summaries


@router.get("/{candidate_id}", response_model=dict[str, Any])
def get_candidate_detail(candidate_id: str):
    """
    Retrieve complete parsed candidate result and full match analysis by candidate ID / scan key.
    """
    filename = f"{candidate_id}.json" if not candidate_id.endswith(".json") else candidate_id
    result = ResultRepository.read_result_by_filename(filename)
    
    if not result:
        # Fallback search by scan_id
        matches = ResultRepository.find_results_by_scan_id(candidate_id)
        if matches:
            first_match = matches[0]
            result = ResultRepository.read_result(first_match)

    if not result:
        raise HTTPException(status_code=404, detail=f"Candidate record '{candidate_id}' not found.")

    return result
