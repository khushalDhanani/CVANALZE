import asyncio
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.recruit import RecruitCandidateMst
from app.services.match_service import MatchService
from app.services.vacancy_service import VacancyService

router = APIRouter(prefix="/batch", tags=["Batch Processing"])

@router.post("/match-candidates")
async def match_candidates_against_vacancies(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Fetch active vacancies and un-evaluated candidates, parse CVs, and match them.
    Cap maximum candidate processing count via MAX_BATCH_LIMIT to prevent API timeouts.
    """
    if limit <= 0 or limit > settings.MAX_BATCH_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Limit must be between 1 and {settings.MAX_BATCH_LIMIT}."
        )

    vacancy_service = VacancyService(db)
    
    # 1. Fetch active vacancies
    job_openings = vacancy_service.get_active_vacancies()
    if not job_openings:
        return {"message": "No active vacancies found.", "matches": []}
        
    # Convert JobOpenings to dicts for the match engine
    job_dicts = [job.model_dump() for job in job_openings]
    
    # 2. Fetch candidates (for demo, just fetch top N active candidates)
    stmt = (
        select(RecruitCandidateMst)
        .where(RecruitCandidateMst.CandidateIsActive == True)
        .where(RecruitCandidateMst.CandidateCVFileName.isnot(None))
        .limit(limit)
    )
    candidates = db.execute(stmt).scalars().all()
    
    if not candidates:
        return {"message": "No candidates with CVs found.", "matches": []}
        
    results = []
    
    # 3. Process candidates
    for candidate in candidates:
        cv_path = Path("uploads") / candidate.CandidateCVFileName
        cv_text = ""
        
        # Read CV text
        if cv_path.exists() and cv_path.is_file():
            try:
                cv_text = cv_path.read_text(errors='ignore')
            except Exception:
                cv_text = f"Candidate {candidate.CandidateFirstName} {candidate.CandidateLastName} CV Placeholder Text."
        else:
            cv_text = f"Mock CV text for {candidate.CandidateFirstName} {candidate.CandidateLastName} with {candidate.CandidateTotExperience} years of experience."

        # Pass metadata to MatchService
        analysis = await MatchService.analyze_single_cv(
            cv_text=cv_text,
            job_openings=job_dicts,
            candidate_id=str(candidate.CandidateID) if candidate.CandidateID is not None else "",
            candidate_experience=float(candidate.CandidateTotExperience) if candidate.CandidateTotExperience else None,
            candidate_ctc=float(candidate.CandidateExpectedCtc) if candidate.CandidateExpectedCtc else None
        )
        
        results.append({
            "candidate_id": candidate.CandidateID,
            "candidate_name": f"{candidate.CandidateFirstName} {candidate.CandidateLastName}",
            "analysis": analysis.model_dump()
        })
        
    return {
        "message": f"Processed {len(results)} candidates against {len(job_openings)} vacancies.",
        "matches": results
    }


@router.websocket("/ws/progress")
async def websocket_progress_endpoint(websocket: WebSocket):
    await websocket.accept()
    redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
    
    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe("cv_processing_progress")
        
        while True:
            # Poll for new messages (we use get_message with timeout instead of listen() to check for disconnects)
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                await websocket.send_text(message["data"])
            
            # This small sleep allows checking if client disconnected
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        print("Client disconnected from /ws/progress")
    except Exception as e:
        print(f"WebSocket Error: {e}")
    finally:
        await pubsub.unsubscribe("cv_processing_progress")
        await pubsub.close()
        await redis_client.aclose()
