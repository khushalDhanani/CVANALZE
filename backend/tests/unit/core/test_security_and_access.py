from __future__ import annotations

import time
import pytest

from app.core.access_policy import resolve_access_tier
from app.core.config import settings
from app.core.security import (
    AuthenticatedPrincipal,
    _role_allows,
    authenticate_api_key,
    authenticate_session_token,
    create_session_token,
)
from app.schemas.contracts import AccessTier


def test_api_key_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RECRUITER_API_KEYS", ["recruiter-secret-1"])
    monkeypatch.setattr(settings, "ADMINISTRATOR_API_KEYS", ["admin-secret-1"])

    # Valid Recruiter
    principal_recruiter = authenticate_api_key("recruiter-secret-1")
    assert principal_recruiter is not None
    assert principal_recruiter.role == AccessTier.RECRUITER
    assert len(principal_recruiter.key_fingerprint) == 16

    # Valid Admin
    principal_admin = authenticate_api_key("admin-secret-1")
    assert principal_admin is not None
    assert principal_admin.role == AccessTier.ADMINISTRATOR

    # Invalid Key
    assert authenticate_api_key("invalid-unknown-key") is None
    assert authenticate_api_key("") is None
    assert authenticate_api_key(None) is None


def test_session_token_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings,
        "AUTH_SESSION_SIGNING_KEY",
        "super-secret-signing-key-minimum-32-chars-long-123456",
    )
    monkeypatch.setattr(settings, "AUTH_SESSION_TTL_SECONDS", 3600)

    principal = AuthenticatedPrincipal(role=AccessTier.RECRUITER, key_fingerprint="abc123def456")
    token = create_session_token(principal)
    assert isinstance(token, str)
    assert "." in token

    # Verify valid token
    decoded_principal = authenticate_session_token(token)
    assert decoded_principal is not None
    assert decoded_principal.role == AccessTier.RECRUITER
    assert decoded_principal.key_fingerprint == "abc123def456"


def test_session_token_tampering_and_expiration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings,
        "AUTH_SESSION_SIGNING_KEY",
        "super-secret-signing-key-minimum-32-chars-long-123456",
    )
    principal = AuthenticatedPrincipal(role=AccessTier.ADMINISTRATOR, key_fingerprint="admin123fingerprint")
    token = create_session_token(principal)

    # Tampered signature
    tampered_token = token[:-5] + "XXXXX"
    assert authenticate_session_token(tampered_token) is None

    # Expired token
    now_past = int(time.time()) + 100000
    assert authenticate_session_token(token, now=now_past) is None


def test_access_tier_resolution() -> None:
    assert resolve_access_tier("GET", "/") == AccessTier.PUBLIC
    assert resolve_access_tier("GET", "/health") == AccessTier.PUBLIC
    assert resolve_access_tier("POST", "/api/cv/upload") == AccessTier.RECRUITER
    assert resolve_access_tier("GET", "/api/candidates") == AccessTier.RECRUITER
    assert resolve_access_tier("GET", "/api/config/rules") == AccessTier.ADMINISTRATOR
    assert resolve_access_tier("GET", "/api/performance/metrics") == AccessTier.ADMINISTRATOR


def test_role_hierarchy_permissions() -> None:
    assert _role_allows(AccessTier.ADMINISTRATOR, AccessTier.ADMINISTRATOR) is True
    assert _role_allows(AccessTier.ADMINISTRATOR, AccessTier.RECRUITER) is True
    assert _role_allows(AccessTier.ADMINISTRATOR, AccessTier.PUBLIC) is True

    assert _role_allows(AccessTier.RECRUITER, AccessTier.RECRUITER) is True
    assert _role_allows(AccessTier.RECRUITER, AccessTier.PUBLIC) is True
    assert _role_allows(AccessTier.RECRUITER, AccessTier.ADMINISTRATOR) is False

    assert _role_allows(AccessTier.PUBLIC, AccessTier.PUBLIC) is True
    assert _role_allows(AccessTier.PUBLIC, AccessTier.RECRUITER) is False
