from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.analysis import router as match_router
from app.api.analytics import router as analytics_router
from app.api.batch import router as batch_router
from app.api.candidates import router as candidates_router
from app.api.config import router as config_router
from app.api.cv import router as cv_router
from app.api.domain_knowledge import router as domain_knowledge_router
from app.api.jobs import router as jobs_router
from app.api.master_data import router as master_data_router
from app.api.performance import router as performance_router
from app.api.recommendations import router as recommendations_router
from app.api.talent_graph import router as talent_graph_router
from app.api.vector_db import router as vector_db_router
from app.core.config import settings
from app.core.database import engine, pg_engine
from app.core.error_handlers import register_exception_handlers
from app.core.lifecycle import application_lifespan
from app.core.logging import logger
from app.core.rate_limit import RateLimitMiddleware
from app.core.request_context import RequestContextMiddleware
from app.core.security import AccessControlMiddleware
from app.schemas.contracts import ErrorResponse


_ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Invalid request"},
    401: {"model": ErrorResponse, "description": "Authentication required"},
    403: {"model": ErrorResponse, "description": "Insufficient permissions"},
    404: {"model": ErrorResponse, "description": "Resource not found"},
    409: {"model": ErrorResponse, "description": "Resource conflict"},
    413: {"model": ErrorResponse, "description": "Request body too large"},
    415: {"model": ErrorResponse, "description": "Unsupported media or file type"},
    422: {"model": ErrorResponse, "description": "Request validation failed"},
    429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    500: {"model": ErrorResponse, "description": "Internal error"},
    503: {"model": ErrorResponse, "description": "Required dependency unavailable"},
}


app = FastAPI(
    title="CV Analyzer API",
    version=settings.VERSION,
    lifespan=application_lifespan,
    responses=_ERROR_RESPONSES,
)
register_exception_handlers(app)

# Middleware is applied in reverse registration order. Request IDs wrap every response,
# CORS wraps authentication/rate-limit failures, and authorization remains closest to routes.
app.add_middleware(AccessControlMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.TRUSTED_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID", "X-Correlation-ID"],
    expose_headers=[
        "X-Request-ID",
        "X-Correlation-ID",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "Retry-After",
    ],
)
app.add_middleware(RequestContextMiddleware)

for router in (
    cv_router,
    match_router,
    jobs_router,
    master_data_router,
    batch_router,
    config_router,
    analytics_router,
    vector_db_router,
    domain_knowledge_router,
    talent_graph_router,
    recommendations_router,
    performance_router,
):
    app.include_router(router, prefix="/api")
app.include_router(candidates_router, prefix="/api")
app.include_router(candidates_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "Welcome to CV Analyzer API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    db_status = _database_health(engine, "MSSQL")
    pg_status = _database_health(pg_engine, "PostgreSQL")
    ollama_status = "disabled"
    if settings.LLM_ENABLED or settings.EMBEDDING_ENABLED:
        from app.services.llm_service import OllamaLLMService

        ollama_status = "online" if OllamaLLMService.check_health() else "offline"

    return {
        "status": "ok",
        "version": settings.VERSION,
        "database": db_status,
        "pg_database": pg_status,
        "ollama_llm": ollama_status,
    }


def _database_health(database_engine, label: str) -> str:
    if database_engine is None:
        return "disabled"
    try:
        with database_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "online"
    except Exception as exc:
        logger.error(f"{label} health check failed: {type(exc).__name__}")
        return "offline"
