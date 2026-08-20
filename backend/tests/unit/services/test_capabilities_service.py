import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.services.capabilities_service import CapabilitiesService


def test_capabilities_are_derived_from_runtime_settings(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ALLOWED_EXTENSIONS", {"pdf"})
    monkeypatch.setattr(settings, "ALLOWED_MIME_TYPES", {"pdf": ["application/pdf"]})
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_BYTES", 1234)
    monkeypatch.setattr(settings, "MAX_PDF_PAGES", 42)
    monkeypatch.setattr(settings, "MAX_UPLOAD_FILES_PER_SELECTION", 6)
    monkeypatch.setattr(settings, "BATCH_CANDIDATE_LIMIT_OPTIONS", [3, 7])
    monkeypatch.setattr(settings, "DEFAULT_BATCH_CANDIDATE_LIMIT", 7)
    monkeypatch.setattr(settings, "MAX_BATCH_LIMIT", 9)
    monkeypatch.setattr(settings, "RECOMMENDED_POLL_INTERVAL_MS", 2500)
    monkeypatch.setattr(settings, "RECOMMENDED_MAX_POLL_ATTEMPTS", 77)
    monkeypatch.setattr(settings, "DOCUMENT_PARSER_DISPLAY_NAME", "Configured parser")
    monkeypatch.setattr(settings, "OCR_ENGINE_DISPLAY_NAME", "Configured OCR")
    monkeypatch.setattr(settings, "LLM_PROVIDER_DISPLAY_NAME", "Configured LLM")
    monkeypatch.setattr(settings, "VECTOR_STORE_DISPLAY_NAME", "Configured vectors")
    monkeypatch.setattr(
        settings,
        "PROCESSING_PIPELINE_STAGES",
        [{"id": "queued", "label": "Queued", "description": "Waiting"}],
    )

    capabilities = CapabilitiesService.get_capabilities()

    assert capabilities.upload.extensions == ["pdf"]
    assert capabilities.upload.mime_types == {"pdf": ["application/pdf"]}
    assert capabilities.upload.max_size_bytes == 1234
    assert capabilities.upload.max_pdf_pages == 42
    assert capabilities.upload.max_files_per_selection == 6
    assert capabilities.batch.limit_options == [3, 7]
    assert capabilities.batch.default_limit == 7
    assert capabilities.batch.max_limit == 9
    assert capabilities.polling.interval_ms == 2500
    assert capabilities.polling.max_attempts == 77
    assert capabilities.implementation.document_parser == "Configured parser"
    assert capabilities.implementation.ocr_engine == "Configured OCR"
    assert capabilities.implementation.llm_provider == "Configured LLM"
    assert capabilities.implementation.vector_store == "Configured vectors"
    assert capabilities.pipeline[0].id == "queued"


def test_capabilities_filter_invalid_batch_options(monkeypatch) -> None:
    monkeypatch.setattr(settings, "BATCH_CANDIDATE_LIMIT_OPTIONS", [0, 10, 60, 10])
    monkeypatch.setattr(settings, "MAX_BATCH_LIMIT", 50)

    capabilities = CapabilitiesService.get_capabilities()

    assert capabilities.batch.limit_options == [10]


def test_capability_settings_reject_conflicting_contracts() -> None:
    with pytest.raises(ValidationError, match="BATCH_CANDIDATE_LIMIT_OPTIONS"):
        Settings(
            DEFAULT_BATCH_CANDIDATE_LIMIT=10,
            MAX_BATCH_LIMIT=20,
            BATCH_CANDIDATE_LIMIT_OPTIONS=[5],
        )
    with pytest.raises(ValidationError, match="MIME type"):
        Settings(ALLOWED_EXTENSIONS={"pdf", "txt"})
    with pytest.raises(ValidationError, match="unique, complete"):
        Settings(
            PROCESSING_PIPELINE_STAGES=[
                {"id": "upload", "label": "Upload", "description": "Upload"},
                {"id": "upload", "label": "Again", "description": "Duplicate"},
            ]
        )
