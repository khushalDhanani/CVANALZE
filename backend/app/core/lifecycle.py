from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import init_db, run_auto_migrations
from app.core.logging import logger

_MSSQL_DATABASE_WRITE_PERMISSIONS = {
    "ADMINISTER DATABASE BULK OPERATIONS",
    "CONTROL",
    "DELETE",
    "EXECUTE",
    "INSERT",
    "REFERENCES",
    "TAKE OWNERSHIP",
    "UPDATE",
}
_MSSQL_SERVER_WRITE_PERMISSIONS = {
    "CONTROL SERVER",
    "CREATE ANY DATABASE",
    "EXTERNAL ACCESS ASSEMBLY",
    "IMPERSONATE ANY LOGIN",
    "SHUTDOWN",
    "UNSAFE ASSEMBLY",
}
_MSSQL_SCOPED_WRITE_PERMISSIONS = {
    "ALTER",
    "CONTROL",
    "DELETE",
    "EXECUTE",
    "INSERT",
    "REFERENCES",
    "TAKE OWNERSHIP",
    "UPDATE",
}


@asynccontextmanager
async def application_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Own startup initialization and process-level resource cleanup."""
    await asyncio.to_thread(initialize_database_schema)
    verify_runtime_security()
    await asyncio.to_thread(verify_mssql_readonly)
    await asyncio.to_thread(verify_redis)
    await asyncio.to_thread(verify_ollama_models)
    # Keep the configuration control plane available on a clean database. CV operations
    # remain fail-closed until a validated PostgreSQL profile is activated.
    from app.core.rule_config_readiness import try_load_active_rule_config
    try_load_active_rule_config(process_name="STARTUP")
        
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
    if settings.AUTH_REQUIRED and len(settings.AUTH_SESSION_SIGNING_KEY.encode("utf-8")) < 32:
        logger.error("[STARTUP] Browser sessions require AUTH_SESSION_SIGNING_KEY with at least 32 characters; session creation will fail closed.")
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
            if OllamaLLMService.is_model_available(model, models):
                logger.info(f"[STARTUP] Ollama {purpose} model '{model}' verified successfully.")
            else:
                if settings.IS_PRODUCTION:
                    raise RuntimeError(f"Configured {purpose} model '{model}' is unavailable in production.")
                logger.error(f"[STARTUP] Configured {purpose} model '{model}' is unavailable. Run: ollama pull {model}")
    except RuntimeError:
        if settings.IS_PRODUCTION:
            raise
        logger.warning("[STARTUP] Could not verify Ollama status: RuntimeError")
    except Exception as exc:
        if settings.IS_PRODUCTION:
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
        from app.repositories.llm_trace import LLMTraceRepository
        from app.services.cache_warmer import warm_all

        warm_all()
        LLMTraceRepository.purge_expired()
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
    from sqlalchemy import text

    from app.core.database import mssql_read_engine

    if not mssql_read_engine:
        return
    try:
        with mssql_read_engine.connect() as conn:
            permissions = _find_mssql_write_permissions(conn, text)
    except Exception as exc:
        message = f"MSSQL read-only permission verification failed ({type(exc).__name__}); startup cannot confirm that the credential is safe."
        if settings.MSSQL_READONLY_ENFORCEMENT:
            logger.error("[STARTUP] %s", message)
            raise RuntimeError(message) from exc
        logger.warning("[STARTUP] SECURITY WARNING: %s Enforcement is disabled for local development.", message)
        return

    if not permissions:
        logger.info("[STARTUP] MSSQL credential verified as read-only.")
        return

    permission_list = ", ".join(sorted(permissions))
    message = f"MSSQL credential has write-capable permission(s): {permission_list}. Use a dedicated credential with only required SELECT access."
    if settings.MSSQL_READONLY_ENFORCEMENT:
        logger.error("[STARTUP] SECURITY ERROR: %s", message)
        raise RuntimeError(message)
    logger.warning("[STARTUP] SECURITY WARNING: %s Enforcement is disabled for local development.", message)


def _find_mssql_write_permissions(conn, sql_text) -> set[str]:
    database_permissions = _permission_names(conn.execute(sql_text("SELECT permission_name FROM fn_my_permissions(NULL, 'DATABASE')")))
    server_permissions = _permission_names(conn.execute(sql_text("SELECT permission_name FROM fn_my_permissions(NULL, 'SERVER')")))
    if "CONTROL SERVER" in server_permissions:
        return {"CONTROL SERVER"}
    if "CONTROL" in database_permissions:
        return {"CONTROL"}
    write_permissions = {
        permission for permission in database_permissions
        if permission.startswith(("ALTER", "CREATE")) or permission in _MSSQL_DATABASE_WRITE_PERMISSIONS
    }
    write_permissions.update(
        permission for permission in server_permissions
        if permission.startswith("ALTER") or permission in _MSSQL_SERVER_WRITE_PERMISSIONS
    )
    if write_permissions:
        return write_permissions

    scoped_query = sql_text(
        """
        SELECT DISTINCT permission_name
        FROM (
            SELECT permissions.permission_name
            FROM sys.schemas AS schemas
            CROSS APPLY fn_my_permissions(QUOTENAME(schemas.name), 'SCHEMA') AS permissions
            WHERE schemas.schema_id < 16384
            UNION ALL
            SELECT permissions.permission_name
            FROM sys.objects AS objects
            INNER JOIN sys.schemas AS schemas ON schemas.schema_id = objects.schema_id
            CROSS APPLY fn_my_permissions(QUOTENAME(schemas.name) + '.' + QUOTENAME(objects.name), 'OBJECT') AS permissions
            WHERE objects.is_ms_shipped = 0
        ) AS effective_permissions
        WHERE permission_name IN ('ALTER', 'CONTROL', 'DELETE', 'EXECUTE', 'INSERT', 'REFERENCES', 'TAKE OWNERSHIP', 'UPDATE')
        """
    )
    return _permission_names(conn.execute(scoped_query)) & _MSSQL_SCOPED_WRITE_PERMISSIONS


def _permission_names(rows) -> set[str]:
    return {str(row[0]).strip().upper() for row in rows if row[0]}
