from __future__ import annotations
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
    await asyncio.to_thread(verify_mssql_readonly)
    await asyncio.to_thread(verify_redis)
    await asyncio.to_thread(verify_ollama_models)
    # Load and validate dynamic database rule configuration
    from app.core.rule_config_manager import RuleConfigManager
    try:
        RuleConfigManager.load_config(tenant_id=None)
        logger.info("[STARTUP] Database rule configuration loaded and validated successfully.")
    except Exception as exc:
        logger.error(f"[STARTUP] Could not load active PostgreSQL rule configuration: {exc}")
        raise RuntimeError("Application cannot start without an active PostgreSQL rule configuration") from exc
        
    # Start the pub/sub listener for hot-reloads
    from app.core.config_listener import start_config_invalidation_listener
    start_config_invalidation_listener()
    
    start_cache_warmup()
    try:
        yield
    finally:
        close_ollama_lifecycle()


def initialize_database_schema() -> None:
    """Allow local initialization only; production schema changes require the migration CLI."""
    if settings.IS_PRODUCTION:
        if settings.INITIALIZE_DATABASE_ON_STARTUP or settings.AUTO_MIGRATE:
            logger.warning("[STARTUP] Production schema initialization flags are ignored; run the migration CLI explicitly.")
        return
    if settings.INITIALIZE_DATABASE_ON_STARTUP:
        init_db()
    if settings.AUTO_MIGRATE:
        run_auto_migrations()


def verify_runtime_security() -> None:
    if settings.AUTH_REQUIRED and not settings.RECRUITER_API_KEYS and not settings.ADMINISTRATOR_API_KEYS:
        logger.error("[STARTUP] Authentication is required but no API keys are configured; protected endpoints will fail closed.")
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
            if settings.IS_PRODUCTION:
                logger.error(f"[STARTUP] Redis ping failed ({type(exc).__name__}) in production.")
                raise RuntimeError("Redis is required in production environment but is unreachable.") from exc
            logger.warning(f"[STARTUP] Redis ping failed ({type(exc).__name__}). Operating with L1 memory and file caching fallback.")
            return
    if settings.IS_PRODUCTION:
        raise RuntimeError("Redis is required in production environment but is not configured.")
    logger.warning("[STARTUP] Redis is not active or reachable. Operating with L1 memory and file caching fallback.")


def verify_ollama_models() -> None:
    if not settings.LLM_ENABLED and not settings.EMBEDDING_ENABLED:
        return
    try:
        from app.services.llm_service import OllamaLLMService

        models = OllamaLLMService.get_available_models()
        if not models:
            if settings.IS_PRODUCTION:
                raise RuntimeError("Ollama returned no models or is unreachable in production environment.")
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
                if settings.IS_PRODUCTION:
                    raise RuntimeError(f"Configured {purpose} model '{model}' is unavailable in production.")
                logger.error(f"[STARTUP] Configured {purpose} model '{model}' is unavailable. Run: ollama pull {model}")
    except Exception as exc:
        if settings.IS_PRODUCTION and not isinstance(exc, RuntimeError):
            raise RuntimeError(f"Could not verify Ollama status in production: {type(exc).__name__}") from exc
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
        if settings.OLLAMA_UNLOAD_ON_SHUTDOWN:
            models: set[str] = set()
            if settings.LLM_ENABLED:
                models.add(settings.OLLAMA_MODEL)
            if settings.EMBEDDING_ENABLED:
                models.add(settings.EMBEDDING_MODEL)
            for model in models:
                OllamaLLMService.unload_model(model)
    finally:
        OllamaLLMService.close_transport()


def verify_mssql_readonly() -> None:
    from app.core.database import mssql_read_engine
    from sqlalchemy import text
    
    if mssql_read_engine:
        try:
            with mssql_read_engine.connect() as conn:
                result = conn.execute(text("SELECT permission_name FROM fn_my_permissions(NULL, 'DATABASE')"))
                permissions = {row[0].upper() for row in result}
                forbidden = {"INSERT", "UPDATE", "DELETE", "CREATE TABLE", "DROP TABLE"}
                if permissions.intersection(forbidden):
                    logger.error("[STARTUP] SECURITY WARNING: MSSQL connection has write permissions! This application expects a read-only credential.")
                    raise RuntimeError("SECURITY WARNING: MSSQL connection has write permissions! This application expects a read-only credential.")
        except Exception as exc:
            logger.warning(f"[STARTUP] Could not verify MSSQL read-only permissions: {type(exc).__name__}")
