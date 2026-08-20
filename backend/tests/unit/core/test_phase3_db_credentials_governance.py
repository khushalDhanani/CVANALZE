"""
Unit tests for Phase 3 Database Credentials & Profile Validation Governance.

Verifies:
1. Local development profile permits default development connection URLs.
2. Production profile (ENVIRONMENT='production') rejects default local passwords (e.g. postgres:postgres@localhost).
3. Production profile rejects unencrypted POSTGRES_SSL_MODE='disable'.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_development_profile_permits_default_credentials():
    """Verify development profile permits default local URLs."""
    dev_settings = Settings(
        APP_ENVIRONMENT="development",
        POSTGRES_APP_URL="postgresql://postgres:postgres@localhost:5432/cv_analyzer",
        REDIS_URL="redis://localhost:6379/0",
    )
    assert dev_settings.IS_PRODUCTION is False


def test_production_profile_rejects_default_postgres_credentials():
    """Verify production profile rejects postgres:postgres@localhost default credentials."""
    with pytest.raises((ValueError, ValidationError), match="default local development credentials"):
        Settings(
            APP_ENVIRONMENT="production",
            POSTGRES_APP_URL="postgresql://postgres:postgres@localhost:5432/cv_analyzer",
            REDIS_URL="redis://prod-redis.internal:6379/0",
            MSSQL_READ_ONLY_URL="mssql+pyodbc://prod_user:secret@prod-sql.internal:1433/db",
            AUTH_SESSION_SIGNING_KEY="secure_prod_key_1234567890",
            POSTGRES_SSL_MODE="require",
        )


def test_production_profile_rejects_default_redis_url():
    """Verify production profile rejects redis://localhost:6379 default endpoint."""
    with pytest.raises((ValueError, ValidationError), match="default local development endpoint"):
        Settings(
            APP_ENVIRONMENT="production",
            POSTGRES_APP_URL="postgresql://app_user:secure_pwd@prod-db.internal:5432/cv_analyzer",
            REDIS_URL="redis://localhost:6379/0",
            MSSQL_READ_ONLY_URL="mssql+pyodbc://prod_user:secret@prod-sql.internal:1433/db",
            AUTH_SESSION_SIGNING_KEY="secure_prod_key_1234567890",
            POSTGRES_SSL_MODE="require",
        )


def test_production_profile_rejects_unencrypted_ssl_mode():
    """Verify production profile rejects POSTGRES_SSL_MODE='disable'."""
    with pytest.raises((ValueError, ValidationError), match="POSTGRES_SSL_MODE must require encryption"):
        Settings(
            APP_ENVIRONMENT="production",
            POSTGRES_APP_URL="postgresql://app_user:secure_pwd@prod-db.internal:5432/cv_analyzer",
            REDIS_URL="redis://prod-redis.internal:6379/0",
            MSSQL_READ_ONLY_URL="mssql+pyodbc://prod_user:secret@prod-sql.internal:1433/db",
            AUTH_SESSION_SIGNING_KEY="secure_prod_key_1234567890",
            POSTGRES_SSL_MODE="disable",
        )
