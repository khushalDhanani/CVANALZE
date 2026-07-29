import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analysis import router as match_router
from app.api.batch import router as batch_router
from app.api.candidates import router as candidates_router
from app.api.config import router as config_router
from app.api.cv import router as cv_router
from app.api.jobs import router as jobs_router
from app.core.config import settings
from app.core.database import engine, init_db

# Initialize database tables if missing
init_db()

app = FastAPI(
    title="CV Analyzer API",
    version=settings.VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    cv_router,
    prefix="/api",
)
app.include_router(
    match_router,
    prefix="/api",
)
app.include_router(
    jobs_router,
    prefix="/api",
)
app.include_router(
    batch_router,
    prefix="/api",
)
app.include_router(
    config_router,
    prefix="/api",
)
app.include_router(
    candidates_router,
    prefix="/api/v1",
)



@app.get("/")
async def root():
    return {
        "message": "Welcome to CV Analyzer API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health():
    db_status = "disabled"
    if engine is not None:
        try:
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            db_status = "online"
        except Exception as exc:
            db_status = f"offline: {exc}"

    ollama_status = "disabled"
    if settings.LLM_ENABLED:
        try:
            url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    ollama_status = "online"
                else:
                    ollama_status = f"http_{resp.status_code}"
        except Exception as exc:
            ollama_status = f"offline: {exc}"

    return {
        "status": "ok",
        "version": settings.VERSION,
        "database": db_status,
        "ollama_llm": ollama_status,
    }
