import asyncio
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import init_db, run_auto_migrations
from app.core.logging import logger


@asynccontextmanager
async def application_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Own startup initialization and process-level resource cleanup."""
    await asyncio.to_thread(initialize_database_schema)
    verify_runtime_security()
    await asyncio.to_thread(verify_redis)
    await asyncio.to_thread(verify_ollama_models)
    start_cache_warmup()
    try:
        yield
    finally:
        close_ollama_lifecycle()


def initialize_database_schema() -> None:
    """Allow local initialization only; production schema changes require the migration CLI."""
    if settings.IS_PRODUCTION:
        if settings.INITIALIZE_DATABASE_ON_STARTUP or settings.AUTO_MIGRATE:
            logger.warning(
                "[STARTUP] Production schema initialization flags are ignored; run the migration CLI explicitly."
            )
        return
    if settings.INITIALIZE_DATABASE_ON_STARTUP:
        init_db()
    if settings.AUTO_MIGRATE:
        run_auto_migrations()


def verify_runtime_security() -> None:
    if settings.AUTH_REQUIRED and not settings.RECRUITER_API_KEYS and not settings.ADMINISTRATOR_API_KEYS:
        logger.error(
            "[STARTUP] Authentication is required but no API keys are configured; protected endpoints will fail closed."
        )
    if any(origin.strip() == "*" for origin in settings.ALLOWED_ORIGINS):
        logger.warning("[STARTUP] Wildcard CORS origins are ignored; configure explicit trusted origins.")


def verify_redis() -> None:
    from app.core.cache import _REDIS_CLIENT

    if _REDIS_CLIENT:
        try:
            _REDIS_CLIENT.ping()
            logger.info("[STARTUP] Active Redis instance verified successfully.")
            return
        except Exception as exc:
            logger.warning(
                f"[STARTUP] Redis ping failed ({type(exc).__name__}). "
                "Operating with L1 memory and file caching fallback."
            )
            return
    logger.warning(
        "[STARTUP] Redis is not active or reachable. "
        "Operating with L1 memory and file caching fallback."
    )


def verify_ollama_models() -> None:
    if not settings.LLM_ENABLED and not settings.EMBEDDING_ENABLED:
        return
    try:
        from app.services.llm_service import OllamaLLMService

        models = OllamaLLMService.get_available_models()
        if not models:
            logger.warning("[STARTUP] Ollama returned no models or is unreachable. LLM operations may fail.")
            return
        configured_models: list[tuple[str, str]] = []
        if settings.LLM_ENABLED:
            configured_models.append(("generation", settings.OLLAMA_MODEL))
        if settings.EMBEDDING_ENABLED:
            configured_models.append(("embedding", settings.EMBEDDING_MODEL))
        for purpose, model in configured_models:
            if any(model in available for available in models):
                logger.info(f"[STARTUP] Ollama {purpose} model '{model}' verified successfully.")
            else:
                logger.error(
                    f"[STARTUP] Configured {purpose} model '{model}' is unavailable. "
                    f"Run: ollama pull {model}"
                )
    except Exception as exc:
        logger.warning(f"[STARTUP] Could not verify Ollama status: {type(exc).__name__}")


def start_cache_warmup() -> None:
    if not settings.STARTUP_CACHE_WARMUP_ENABLED:
        return
    thread = threading.Thread(target=_run_cache_warmup, daemon=True, name="cache-warmup")
    thread.start()
    logger.info("[WARMUP] Background cache warmup thread started.")


def _run_cache_warmup() -> None:
    try:
        from app.services.cache_warmer import warm_all

        warm_all()
    except Exception as exc:
        logger.warning(f"[WARMUP] Background warmup failed: {type(exc).__name__}")


def close_ollama_lifecycle() -> None:
    from app.services.llm_service import OllamaLLMService

    try:
        if settings.LLM_ENABLED and settings.OLLAMA_UNLOAD_ON_SHUTDOWN:
            OllamaLLMService.unload_model()
    finally:
        OllamaLLMService.close_transport()
