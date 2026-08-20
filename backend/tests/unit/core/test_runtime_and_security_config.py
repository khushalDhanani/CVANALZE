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

    assert settings.APP_DATA_ROOT in settings.UPLOADS_DIR.parents or settings.UPLOADS_DIR == settings.APP_DATA_ROOT / "uploads"


def test_production_secret_rejection() -> None:
    """Workstream 5.3: Production environments reject known insecure / local default secrets."""
    with pytest.raises(ValueError, match="AUTH_SESSION_SIGNING_KEY"):
        Settings(
            APP_ENVIRONMENT="production",
            AUTH_ENABLED=True,
            AUTH_SESSION_SIGNING_KEY="change_me",
            REDIS_URL="redis://localhost:6379/0",
            MSSQL_READ_ONLY_URL="mssql+pyodbc://localhost/db",
            POSTGRES_APP_URL="postgresql://localhost/db",
        )


def test_database_pool_settings() -> None:
    """Workstream 5.3: Database pool sizes, timeouts, and TLS settings are environment-driven."""
    assert settings.POSTGRES_POOL_SIZE == 10
    assert settings.POSTGRES_MAX_OVERFLOW == 20
    assert settings.POSTGRES_POOL_TIMEOUT == 30.0
    assert settings.POSTGRES_SSL_MODE == "prefer"
    assert settings.MSSQL_POOL_SIZE == 10
    assert settings.MSSQL_MAX_OVERFLOW == 20


def test_frontend_polling_metadata() -> None:
    """Workstream 5.3: Backend config defines frontend lifecycle polling and retry metadata."""
    assert settings.FRONTEND_POLL_INTERVAL_MS == 2000
    assert settings.FRONTEND_RETRY_AFTER_MS == 2000
