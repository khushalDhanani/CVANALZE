from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from app.core.database import get_mssql_read_db
from app.core.error_handlers import SystemConfigurationError
from app.repositories.job import JobRepository, VacancySourceUnavailableError
from app.schemas.job import JobOpening
from app.services.vacancy_service import VacancyService
from app.core.config import settings

router = APIRouter(prefix="/jobs", tags=["Jobs"])

# Existing endpoints ... (will be retained) 

@router.get("/active", response_model=list[JobOpening])
async def list_active_vacancies(db: Session = Depends(get_mssql_read_db)):
    """Retrieve all active vacancies with organization context."""
    try:
        vacancy_service = VacancyService(db)
        return vacancy_service.get_active_vacancies()
    except SystemConfigurationError:
        raise
    except Exception as exc:
        from app.core.logging import logger
        logger.exception(f"Failed to list active vacancies: {exc}")
        raise HTTPException(status_code=503, detail="MSSQL vacancy source is unavailable.") from exc

# Existing routes continue below

# Duplicate router definition removed


@router.get("", response_model=list[JobOpening])
async def list_jobs(response: Response):
    """Retrieve all available job openings."""
    try:
        result = await run_in_threadpool(JobRepository.load_all_jobs)
        response.headers["X-Vacancy-Status"] = result.status.value
        return result.jobs
    except SystemConfigurationError:
        raise
    except VacancySourceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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
    except SystemConfigurationError:
        raise
    except Exception as exc:
        from app.core.logging import logger

        logger.exception(f"Failed to invalidate job cache: {exc}")
        raise HTTPException(status_code=500, detail="Failed to invalidate job cache.") from exc


@router.get("/{job_id}", response_model=JobOpening)
async def get_job(job_id: str):
    """Retrieve a specific job opening by ID."""
    try:
        job = await run_in_threadpool(JobRepository.get_job_by_id, job_id)
    except VacancySourceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
