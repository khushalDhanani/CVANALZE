from __future__ import annotations

from pathlib import Path
import pytest

from app.core.config import Settings, settings


def test_app_data_root_derived_paths() -> None:
    """Workstream 5.3: Derived directories use APP_DATA_ROOT instead of cwd relative paths."""
    assert settings.APP_DATA_ROOT.is_absolute()
    assert settings.UPLOADS_DIR.is_absolute()
    assert settings.RESULTS_DIR.is_absolute()
    assert settings.TRAINING_DATA_DIR.is_absolute()

    assert settings.UPLOADS_DIR == settings.APP_DATA_ROOT
    assert settings.RESULTS_DIR == settings.UPLOADS_DIR / "results"


def test_production_secret_rejection() -> None:
    """Workstream 5.3: Production environments reject known insecure / local default secrets."""
    with pytest.raises(ValueError, match="AUTH_SESSION_SIGNING_KEY"):
        Settings(
            APP_ENVIRONMENT="production",
            AUTH_ENABLED=True,
            AUTH_SESSION_SIGNING_KEY="change_me",
            RECRUITER_API_KEYS=["recruiter-key"],
            ALLOWED_ORIGINS=["https://recruiting.example.com"],
            GIT_SHA="abc1234",
            REDIS_URL="rediss://redis.internal/0",
            MSSQL_READ_ONLY_URL="mssql+pyodbc://reader:secret@sql.internal/db",
            POSTGRES_APP_URL="postgresql://app:secret@postgres.internal/db",
            POSTGRES_SSL_MODE="require",
        )


def test_database_pool_settings() -> None:
    """Workstream 5.3: Database pool sizes, timeouts, and TLS settings are environment-driven."""
    assert settings.POSTGRES_POOL_SIZE == 10
    assert settings.POSTGRES_MAX_OVERFLOW == 20
    assert settings.POSTGRES_POOL_TIMEOUT == 30.0
    assert settings.POSTGRES_SSL_MODE == "prefer"
    assert settings.MSSQL_POOL_SIZE == 10
    assert settings.MSSQL_MAX_OVERFLOW == 20


def test_production_authentication_requires_an_api_key() -> None:
    with pytest.raises(ValueError, match="API key"):
        Settings(
            APP_ENVIRONMENT="production",
            AUTH_ENABLED=True,
            AUTH_SESSION_SIGNING_KEY="secure-signing-key-with-more-than-32-characters",
            RECRUITER_API_KEYS=[],
            ADMINISTRATOR_API_KEYS=[],
            ALLOWED_ORIGINS=["https://recruiting.example.com"],
            GIT_SHA="abc1234",
            REDIS_URL="rediss://redis.internal/0",
            MSSQL_READ_ONLY_URL="mssql+pyodbc://reader:secret@sql.internal/db",
            POSTGRES_APP_URL="postgresql://app:secret@postgres.internal/db",
            POSTGRES_SSL_MODE="require",
        )


def test_production_requires_a_trusted_origin() -> None:
    with pytest.raises(ValueError, match="ALLOWED_ORIGINS"):
        Settings(
            APP_ENVIRONMENT="production",
            AUTH_ENABLED=False,
            ALLOWED_ORIGINS=[],
            GIT_SHA="abc1234",
            REDIS_URL="rediss://redis.internal/0",
            MSSQL_READ_ONLY_URL="mssql+pyodbc://reader:secret@sql.internal/db",
            POSTGRES_APP_URL="postgresql://app:secret@postgres.internal/db",
            POSTGRES_SSL_MODE="require",
        )
