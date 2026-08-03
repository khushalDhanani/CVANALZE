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


def test_concrete_paths_resolve_characterized_access_tiers():
    assert resolve_access_tier("GET", "/") == AccessTier.PUBLIC
    assert resolve_access_tier("GET", "/api/candidates/candidate-123") == AccessTier.RECRUITER
    assert resolve_access_tier("POST", "/api/candidates/candidate-123/reprocess") == AccessTier.ADMINISTRATOR
    assert resolve_access_tier("POST", "/api/match/hr-review") == AccessTier.RECRUITER
    assert resolve_access_tier("PUT", "/api/config/match") == AccessTier.ADMINISTRATOR
    assert resolve_access_tier("POST", "/api/master-data/warm") == AccessTier.ADMINISTRATOR
    assert resolve_access_tier("POST", "/api/vector-db/sync") == AccessTier.ADMINISTRATOR


def test_trusted_cors_configuration_never_contains_wildcard():
    assert "*" not in settings.TRUSTED_ORIGINS


def test_authentication_and_role_authorization(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "RECRUITER_API_KEYS", ["recruiter-secret"])
    monkeypatch.setattr(settings, "ADMINISTRATOR_API_KEYS", ["administrator-secret"])
    client = TestClient(_app_with_operational_middleware("/api/config/match"))

    unauthorized = client.get("/api/config/match", headers={"X-Request-ID": "request-auth"})
    forbidden = client.get("/api/config/match", headers={"Authorization": "Bearer recruiter-secret"})
    allowed = client.get("/api/config/match", headers={"X-API-Key": "administrator-secret"})

    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "UNAUTHORIZED"
    assert unauthorized.json()["error"]["request_id"] == "request-auth"
    assert unauthorized.headers["X-Request-ID"] == "request-auth"
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"
    assert allowed.status_code == 200


def test_production_authentication_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    monkeypatch.setattr(settings, "RECRUITER_API_KEYS", ["recruiter-secret"])
    monkeypatch.setattr(settings, "ADMINISTRATOR_API_KEYS", [])
    client = TestClient(_app_with_operational_middleware("/api/candidates"))

    response = client.get("/api/candidates")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_unhandled_exception_returns_stable_envelope_without_trace(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/boom")
    async def boom():
        raise RuntimeError(
            "private stack detail /Users/operator/cv-analyzer secret-token raw.person@example.com"
        )

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
