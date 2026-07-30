from fastapi import APIRouter, HTTPException

from app.repositories.job import JobRepository
from app.schemas.job import JobOpening

router = APIRouter(prefix="/jobs", tags=["Jobs"])


from fastapi.concurrency import run_in_threadpool

@router.get("", response_model=list[JobOpening])
async def list_jobs():
    """Retrieve all available job openings."""
    try:
        return await run_in_threadpool(JobRepository.get_all_jobs)
    except Exception as exc:
        from app.core.logging import logger
        logger.exception(f"Failed to list jobs: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job listings.") from exc


@router.post("/cache/invalidate")
async def invalidate_jobs_cache():
    """Clear the job repository cache (to be called on create/update/close events)."""
    try:
        await run_in_threadpool(JobRepository.invalidate_cache)
        
        # Hook into vacancy create/update path for ongoing sync
        from app.core.tasks import sync_all_vacancies
        await run_in_threadpool(sync_all_vacancies)
        
        return {"message": "Job cache invalidated and embedding sync enqueued successfully"}
    except Exception as exc:
        from app.core.logging import logger
        logger.exception(f"Failed to invalidate job cache: {exc}")
        raise HTTPException(status_code=500, detail="Failed to invalidate job cache.") from exc


@router.get("/{job_id}", response_model=JobOpening)
async def get_job(job_id: str):
    """Retrieve a specific job opening by ID."""
    job = await run_in_threadpool(JobRepository.get_job_by_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
