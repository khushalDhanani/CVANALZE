import json
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.access_policy import resolve_access_tier
from app.core.config import settings
from app.core.error_handlers import register_exception_handlers
from app.core.rate_limit import RateLimitMiddleware
from app.core.request_context import RequestContextMiddleware
from app.core.security import AccessControlMiddleware
from app.core.security import AuthenticatedPrincipal, authenticate_session_token, create_session_token
from app.api.auth import router as auth_router
import app.main as main_module
from app.main import app as main_app
from app.schemas.analysis import HRReviewRequest
from app.schemas.contracts import AccessTier
from app.schemas.cv import CVMatchRequest


def _app_with_operational_middleware(path: str = "/test") -> FastAPI:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get(path)
    async def endpoint():
        return {"status": "ok"}

    test_app.add_middleware(AccessControlMiddleware)
    test_app.add_middleware(RequestContextMiddleware)
    return test_app


def _app_with_session_auth() -> FastAPI:
    test_app = FastAPI()
    register_exception_handlers(test_app)
    test_app.include_router(auth_router, prefix="/api")

    @test_app.get("/api/candidates")
    async def candidates():
        return {"status": "ok"}

    @test_app.get("/api/config/active")
    async def active_config():
        return {"status": "ok"}

    test_app.add_middleware(AccessControlMiddleware)
    test_app.add_middleware(RequestContextMiddleware)
    return test_app


@pytest.mark.asyncio
async def test_health_reports_configured_dependencies_online(monkeypatch):
    monkeypatch.setattr(main_module, "_database_health", lambda _engine, _label: "online")
    monkeypatch.setattr(main_module, "_redis_health", lambda: "online")
    monkeypatch.setattr(main_module, "_rule_config_health", lambda: "online")
    monkeypatch.setattr(settings, "LLM_ENABLED", False)
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", False)

    response = await main_module.health()
    payload = json.loads(response.body)

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["database"] == "online"
    assert payload["pg_database"] == "online"
    assert payload["redis"] == "online"
    assert payload["ollama_llm"] == "disabled"
    assert payload["rule_configuration"] == "online"


@pytest.mark.asyncio
async def test_health_returns_service_unavailable_for_offline_dependency(monkeypatch):
    def database_health(_engine, label):
        return "offline" if label == "PostgreSQL" else "online"

    monkeypatch.setattr(main_module, "_database_health", database_health)
    monkeypatch.setattr(main_module, "_redis_health", lambda: "online")
    monkeypatch.setattr(main_module, "_rule_config_health", lambda: "online")
    monkeypatch.setattr(settings, "LLM_ENABLED", False)
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", False)

    response = await main_module.health()
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert payload["status"] == "unhealthy"
    assert payload["database"] == "online"
    assert payload["pg_database"] == "offline"
    assert payload["redis"] == "online"


@pytest.mark.asyncio
async def test_health_requires_ollama_when_llm_capability_is_enabled(monkeypatch):
    from app.services.llm_service import OllamaLLMService

    monkeypatch.setattr(main_module, "_database_health", lambda _engine, _label: "online")
    monkeypatch.setattr(main_module, "_redis_health", lambda: "online")
    monkeypatch.setattr(main_module, "_rule_config_health", lambda: "online")
    monkeypatch.setattr(settings, "LLM_ENABLED", True)
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", False)
    monkeypatch.setattr(OllamaLLMService, "check_health", classmethod(lambda _cls: False))

    response = await main_module.health()
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert payload["status"] == "unhealthy"
    assert payload["ollama_llm"] == "offline"


@pytest.mark.asyncio
async def test_health_is_unavailable_without_active_rule_configuration(monkeypatch):
    monkeypatch.setattr(main_module, "_database_health", lambda _engine, _label: "online")
    monkeypatch.setattr(main_module, "_redis_health", lambda: "online")
    monkeypatch.setattr(main_module, "_rule_config_health", lambda: "unavailable")
    monkeypatch.setattr(settings, "LLM_ENABLED", False)
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", False)

    response = await main_module.health()
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert payload["status"] == "unhealthy"
    assert payload["rule_configuration"] == "unavailable"


def test_redis_health_distinguishes_disabled_and_unavailable(monkeypatch):
    from app.core import cache

    monkeypatch.setattr(settings, "REDIS_URL", None)
    assert main_module._redis_health() == "disabled"

    monkeypatch.setattr(settings, "REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setattr(cache, "_REDIS_CLIENT", None)
    assert main_module._redis_health() == "offline"


def test_concrete_paths_resolve_characterized_access_tiers():
    assert resolve_access_tier("GET", "/") == AccessTier.PUBLIC
    assert resolve_access_tier("GET", "/api/candidates/candidate-123") == AccessTier.RECRUITER
    assert resolve_access_tier("POST", "/api/candidates/candidate-123/reprocess") == AccessTier.ADMINISTRATOR
    assert resolve_access_tier("POST", "/api/match/hr-review") == AccessTier.RECRUITER
    assert resolve_access_tier("POST", "/api/master-data/warm") == AccessTier.ADMINISTRATOR
    assert resolve_access_tier("POST", "/api/vector-db/sync") == AccessTier.ADMINISTRATOR
    assert resolve_access_tier("GET", "/api/batch/jobs/batch-123") == AccessTier.RECRUITER
    assert resolve_access_tier("GET", "/api/config/schema") == AccessTier.ADMINISTRATOR
    assert resolve_access_tier("GET", "/api/config/system-default") == AccessTier.ADMINISTRATOR
    assert resolve_access_tier("GET", "/api/config/rules") == AccessTier.ADMINISTRATOR
    assert resolve_access_tier("POST", "/api/config/initialize") == AccessTier.ADMINISTRATOR


def test_trusted_cors_configuration_never_contains_wildcard():
    assert "*" not in settings.TRUSTED_ORIGINS


def test_authentication_and_role_authorization(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "RECRUITER_API_KEYS", ["recruiter-secret"])
    monkeypatch.setattr(settings, "ADMINISTRATOR_API_KEYS", ["administrator-secret"])
    monkeypatch.setattr(settings, "AUTH_SESSION_SIGNING_KEY", "test-session-signing-secret-value-32")
    client = TestClient(_app_with_operational_middleware("/api/config/active"))

    unauthorized = client.get("/api/config/active", headers={"X-Request-ID": "request-auth"})
    forbidden = client.get("/api/config/active", headers={"Authorization": "Bearer recruiter-secret"})
    allowed = client.get("/api/config/active", headers={"X-API-Key": "administrator-secret"})

    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "UNAUTHORIZED"
    assert unauthorized.json()["error"]["request_id"] == "request-auth"
    assert unauthorized.headers["X-Request-ID"] == "request-auth"
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"
    assert allowed.status_code == 200


def test_authentication_disabled_bypasses_protected_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    monkeypatch.setattr(settings, "RECRUITER_API_KEYS", ["recruiter-secret"])
    monkeypatch.setattr(settings, "ADMINISTRATOR_API_KEYS", [])
    monkeypatch.setattr(settings, "AUTH_SESSION_SIGNING_KEY", "test-session-signing-secret-value-32")
    client = TestClient(_app_with_operational_middleware("/api/jobs"))

    response = client.get("/api/jobs")

    assert settings.AUTH_REQUIRED is False
    assert response.status_code == 200


def test_authentication_enabled_protects_endpoint_and_accepts_valid_credentials(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "RECRUITER_API_KEYS", ["recruiter-secret"])
    monkeypatch.setattr(settings, "ADMINISTRATOR_API_KEYS", [])
    client = TestClient(_app_with_operational_middleware("/api/jobs"))

    unauthorized = client.get("/api/jobs")
    authenticated = client.get("/api/jobs", headers={"Authorization": "Bearer recruiter-secret"})

    assert settings.AUTH_REQUIRED is True
    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "UNAUTHORIZED"
    assert authenticated.status_code == 200


def test_frontend_exchanges_api_key_for_secure_session_cookie(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "RECRUITER_API_KEYS", ["recruiter-secret"])
    monkeypatch.setattr(settings, "ADMINISTRATOR_API_KEYS", ["administrator-secret"])
    monkeypatch.setattr(settings, "AUTH_SESSION_SIGNING_KEY", "test-session-signing-secret-value-32")
    client = TestClient(_app_with_session_auth(), base_url="https://api.example.test")

    login = client.post("/api/auth/session", headers={"X-API-Key": "recruiter-secret"})

    assert login.status_code == 200
    assert login.json()["role"] == "recruiter"
    cookie = login.headers["set-cookie"]
    assert "cv_analyzer_session=" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=strict" in cookie
    assert "recruiter-secret" not in cookie
    assert client.get("/api/candidates").status_code == 200
    assert client.get("/api/config/active").status_code == 403

    logout = client.delete("/api/auth/session")

    assert logout.status_code == 200
    assert client.get("/api/candidates").status_code == 401


def test_signed_session_rejects_expiry_and_tampering(monkeypatch):
    monkeypatch.setattr(settings, "RECRUITER_API_KEYS", ["recruiter-secret"])
    monkeypatch.setattr(settings, "ADMINISTRATOR_API_KEYS", [])
    monkeypatch.setattr(settings, "AUTH_SESSION_SIGNING_KEY", "test-session-signing-secret-value-32")
    monkeypatch.setattr(settings, "AUTH_SESSION_TTL_SECONDS", 60)
    principal = AuthenticatedPrincipal(AccessTier.RECRUITER, "fingerprint")
    token = create_session_token(principal, issued_at=100)

    assert authenticate_session_token(token, now=159) == principal
    assert authenticate_session_token(token, now=160) is None
    tampered_token = ("A" if token[0] != "A" else "B") + token[1:]
    assert authenticate_session_token(tampered_token, now=159) is None


def test_unhandled_exception_returns_stable_envelope_without_trace(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/boom")
    async def boom():
        raise RuntimeError("private stack detail /Users/operator/cv-analyzer secret-token raw.person@example.com")

    test_app.add_middleware(RequestContextMiddleware)
    client = TestClient(test_app, raise_server_exceptions=False)

    response = client.get(
        "/boom",
        headers={"X-Request-ID": "request-123", "X-Correlation-ID": "correlation-456"},
    )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "request-123"
    assert response.headers["X-Correlation-ID"] == "correlation-456"
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An internal error occurred.",
            "request_id": "request-123",
            "correlation_id": "correlation-456",
            "retryable": False,
            "details": {},
        },
        "detail": "An internal error occurred.",
    }
    assert "private stack detail" not in response.text
    assert "/Users/operator" not in response.text
    assert "secret-token" not in response.text
    assert "raw.person@example.com" not in response.text


def test_framework_not_found_uses_stable_error_envelope():
    test_app = FastAPI()
    register_exception_handlers(test_app)
    test_app.add_middleware(RequestContextMiddleware)

    response = TestClient(test_app).get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


def test_validation_envelope_omits_submitted_cv_text(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.post("/cv")
    async def accept_cv(payload: CVMatchRequest):
        return payload

    test_app.add_middleware(RequestContextMiddleware)
    client = TestClient(test_app)
    private_text = "x" * (settings.MAX_CV_TEXT_LENGTH_CHARS + 1)

    response = client.post("/cv", json={"cv_text": private_text})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert private_text not in response.text


def test_json_content_length_limit_returns_413(monkeypatch):
    monkeypatch.setattr(settings, "MAX_JSON_REQUEST_SIZE_BYTES", 16)
    test_app = _app_with_operational_middleware("/json")
    client = TestClient(test_app)

    response = client.post(
        "/json",
        content=b'{"payload":"this body is too large"}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_raw_cv_and_feedback_models_enforce_length_constraints():
    with pytest.raises(ValidationError):
        CVMatchRequest(cv_text="x" * (settings.MAX_CV_TEXT_LENGTH_CHARS + 1))
    with pytest.raises(ValidationError):
        HRReviewRequest(
            scan_id="scan-1",
            job_id="job-1",
            feedback_notes="x" * (settings.MAX_HR_FEEDBACK_LENGTH_CHARS + 1),
        )


def test_rate_limit_returns_stable_429(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_REQUESTS", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)
    test_app = FastAPI()

    @test_app.get("/limited")
    async def limited():
        return {"status": "ok"}

    test_app.add_middleware(RateLimitMiddleware)
    test_app.add_middleware(RequestContextMiddleware)
    client = TestClient(test_app)

    assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 200
    response = client.get("/limited")

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert int(response.headers["Retry-After"]) >= 1


def test_failed_polling_response_scrubs_historical_traceback(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(
        "app.api.cv.ResultRepository.resolve_result",
        lambda cv_key: {
            "status": "FAILED",
            "message": "CV processing failed.",
            "stage": "parsing",
            "failed_step": "Docling Parsing",
            "error_details": "Traceback (most recent call last): private stack",
        },
    )
    monkeypatch.setattr("app.api.cv.ProcessingJobRepository.get_by_cv_key", lambda cv_key: None)

    response = TestClient(main_app).get("/api/cv/status/cv-failed")

    assert response.status_code == 200
    assert response.json()["error_details"] is None
    assert "Traceback" not in response.text


def test_production_lifecycle_never_mutates_schema(monkeypatch):
    from app.core import lifecycle

    init_db = MagicMock()
    migrate = MagicMock()
    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "INITIALIZE_DATABASE_ON_STARTUP", True)
    monkeypatch.setattr(settings, "AUTO_MIGRATE", True)
    monkeypatch.setattr(lifecycle, "init_db", init_db)
    monkeypatch.setattr(lifecycle, "run_auto_migrations", migrate)

    lifecycle.initialize_database_schema()

    init_db.assert_not_called()
    migrate.assert_not_called()
