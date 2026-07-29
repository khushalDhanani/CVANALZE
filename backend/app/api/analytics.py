from typing import Any
from fastapi import APIRouter

from app.core.cache import _memory_cache, _REDIS_CLIENT
from app.core.metrics import _metrics
from app.core.logging import logger

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/cache", summary="Get Cache Analytics")
async def get_cache_analytics() -> dict[str, Any]:
    """Retrieve cache performance metrics, memory usage, and hit ratios."""
    metrics_report = _metrics.report()

    # Redis Stats
    redis_stats = {"status": "offline"}
    if _REDIS_CLIENT:
        try:
            info = _REDIS_CLIENT.info("memory")
            dbsize = _REDIS_CLIENT.dbsize()
            redis_stats = {
                "status": "online",
                "used_memory_human": info.get("used_memory_human", "0B"),
                "used_memory_bytes": info.get("used_memory", 0),
                "total_keys": dbsize,
            }
        except Exception as exc:
            logger.warning(f"Failed to fetch Redis stats: {exc}")
            redis_stats["status"] = f"error: {exc}"

    # Memory Cache Stats
    memory_cache_stats = {
        "items_count": len(_memory_cache._store),
        "max_size": _memory_cache._max_size,
    }

    return {
        "global_metrics": {
            "total_hits": metrics_report["total_hits"],
            "total_misses": metrics_report["total_misses"],
            "overall_hit_ratio": metrics_report["overall_hit_ratio"],
            "llm_calls_prevented": metrics_report["llm_calls_prevented"],
            "db_queries_prevented": metrics_report["db_queries_prevented"],
        },
        "per_namespace": metrics_report["per_namespace"],
        "system_stats": {
            "redis": redis_stats,
            "memory_cache": memory_cache_stats,
        },
    }
