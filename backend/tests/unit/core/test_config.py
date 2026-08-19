from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


def test_default_settings_initialization() -> None:
    settings = Settings(
        PROJECT_NAME="CV Analyzer",
        ALLOWED_EXTENSIONS={"pdf", "docx"},
    )
    assert settings.PROJECT_NAME == "CV Analyzer"
    assert "pdf" in settings.ALLOWED_EXTENSIONS
    assert "docx" in settings.ALLOWED_EXTENSIONS
    assert settings.MAX_FILE_SIZE_BYTES == 15 * 1024 * 1024
    assert settings.UPLOAD_READ_CHUNK_SIZE_BYTES == 1024 * 1024
    assert settings.RATE_LIMIT_REQUESTS == 300
    assert settings.RATE_LIMIT_WINDOW_SECONDS == 60


def test_settings_security_and_cors() -> None:
    settings = Settings(
        ALLOWED_ORIGINS=["http://localhost:3000", "http://127.0.0.1:8081"],
        AUTH_ENABLED=True,
        RECRUITER_API_KEYS=["recruiter-secret-key-1"],
        ADMINISTRATOR_API_KEYS=["admin-secret-key-1"],
    )
    assert settings.AUTH_ENABLED is True
    assert "http://localhost:3000" in settings.ALLOWED_ORIGINS
    assert len(settings.RECRUITER_API_KEYS) == 1
    assert len(settings.ADMINISTRATOR_API_KEYS) == 1


def test_settings_upload_directories() -> None:
    settings = Settings(
        UPLOADS_DIR=Path("custom_uploads"),
        RESULTS_DIR=Path("custom_uploads/results"),
    )
    assert settings.UPLOADS_DIR == Path("custom_uploads")
    assert settings.RESULTS_DIR == Path("custom_uploads/results")


def test_settings_model_validation_limits() -> None:
    settings = Settings(
        MAX_PDF_PAGES=50,
        MAX_DOCX_ENTRIES=1000,
        MAX_BATCH_LIMIT=100,
    )
    assert settings.MAX_PDF_PAGES == 50
    assert settings.MAX_DOCX_ENTRIES == 1000
    assert settings.MAX_BATCH_LIMIT == 100
