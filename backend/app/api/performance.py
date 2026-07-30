from typing import Any
from pydantic import BaseModel, Field
from fastapi import APIRouter

from app.services.performance_service import EnterprisePerformanceService

router = APIRouter(prefix="/performance", tags=["Enterprise Performance & Observability"])


class CacheInvalidateRequest(BaseModel):
    pattern: str = Field("*", description="Cache key pattern or domain tag to invalidate (e.g., 'vacancies', 'embeddings', '*')")


class CacheInvalidateResponse(BaseModel):
    pattern: str
    cleared: bool
    message: str


@router.get("/metrics", response_model=dict[str, Any])
def get_performance_metrics() -> dict[str, Any]:
    """
    Enterprise Observability Telemetry API.
    Returns real-time telemetry metrics: L1/L2 cache hit ratios, batch throughput,
    retry attempt counts, and 8-stage pipeline latencies.
    """
    return EnterprisePerformanceService.get_performance_metrics()


@router.post("/cache/invalidate", response_model=CacheInvalidateResponse)
def invalidate_cache(request: CacheInvalidateRequest) -> CacheInvalidateResponse:
    """
    Targeted Intelligent Cache Invalidation API.
    Invalidates multi-level LRU memory and shared cache entries matching the requested pattern.
    """
    count = EnterprisePerformanceService.invalidate_cache_by_pattern(request.pattern)
    return CacheInvalidateResponse(
        pattern=request.pattern,
        cleared=True,
        message=f"Successfully invalidated multi-level cache for pattern '{request.pattern}' ({count} scopes cleared).",
    )
