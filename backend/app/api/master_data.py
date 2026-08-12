from __future__ import annotations
from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app.core.cache import master_data_cache_manager

router = APIRouter(prefix="/master-data", tags=["Master Data"])


@router.get("/job-profiles")
async def get_job_profiles():
    cached = master_data_cache_manager.get("job_profiles")
    return cached or []


@router.get("/departments")
async def get_departments():
    cached = master_data_cache_manager.get("departments")
    return cached or []


@router.get("/companies")
async def get_companies():
    cached = master_data_cache_manager.get("companies")
    return cached or []


@router.get("/skills")
async def get_skills():
    cached = master_data_cache_manager.get("skills")
    return cached or []


@router.post("/warm")
async def warm_cache():
    from app.services.cache_warmer import warm_all

    counts = await run_in_threadpool(warm_all)
    return {"message": "Cache warmed", "counts": counts}
