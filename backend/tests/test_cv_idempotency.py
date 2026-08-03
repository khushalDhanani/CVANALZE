import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.services.cv_service import get_stable_cv_key, process_cv_file
from app.services.document_parser import MarkdownGenerator, MarkdownResult


@pytest.fixture(autouse=True)
def clear_caches():
    from app.core.cache import (
        cv_result_cache_manager,
        doc_cache_manager,
        embedding_cache_manager,
    )
    cv_result_cache_manager.clear()
    doc_cache_manager.clear()
    embedding_cache_manager.clear()


@pytest.fixture
def mock_parser_and_engine(monkeypatch):
    extraction_mock = MarkdownResult(
        markdown="# Jane Doe\nSoftware Engineer with Python skills.",
        page_count=1,
        is_scanned=False,
        ocr_applied=False,
    )
    parser_mock = MagicMock(return_value=extraction_mock)
    monkeypatch.setattr(MarkdownGenerator, "generate_with_timeout", parser_mock)

    match_analysis_mock = MagicMock()
    match_analysis_mock.model_dump.return_value = {
        "best_match": {
            "job_title": "Python Developer",
            "score": 90.0,
            "classification": "HIGH",
        }
    }
    match_mock = AsyncMock(return_value=match_analysis_mock)
    from app.services.match_service import MatchService
    from app.services import embedding_service
    from app.services.embedding_service import EmbeddingService
    from app.services.llm_service import OllamaLLMService

    monkeypatch.setattr(MatchService, "analyze_single_cv", match_mock)
    monkeypatch.setattr(EmbeddingService, "generate_embedding", MagicMock(return_value=None))
    monkeypatch.setattr(embedding_service, "get_candidate_embedding", MagicMock(return_value=None))
    monkeypatch.setattr(OllamaLLMService, "unload_model", MagicMock(return_value=True))
    return {"parser": parser_mock, "match": match_mock}


def test_get_stable_cv_key():
    assert get_stable_cv_key("resume.pdf", 101, 501) == "cv_resume"
    assert get_stable_cv_key("resume.pdf", candidate_id=101) == "cv_resume"
    assert get_stable_cv_key("resume.pdf", cv_id=501) == "cv_resume"
    assert get_stable_cv_key("john_doe_cv.pdf") == "cv_john_doe_cv"


@pytest.mark.asyncio
async def test_cv_processing_idempotency_and_cache_hit(tmp_path, monkeypatch, mock_parser_and_engine):
    monkeypatch.setattr(settings, "RESULTS_DIR", tmp_path)

    cv_bytes = b"Dummy CV file content for Jane Doe"
    filename = "jane_doe.pdf"

    # First run: initial processing
    res1 = await process_cv_file(
        filename=filename,
        content=cv_bytes,
        candidate_id="user_123",
        cv_id="cv_456",
    )

    assert res1["status"] == "COMPLETED"
    assert res1["original_status"] == "NEW_CV"
    assert res1["id"] == "cv_jane_doe"
    assert res1["cv_hash"] is not None
    assert res1["created_at"] is not None
    assert res1["updated_at"] is not None
    assert mock_parser_and_engine["parser"].call_count == 1
    assert mock_parser_and_engine["match"].await_count == 1

    expected_json_path = tmp_path / "cv_jane_doe.json"
    assert expected_json_path.is_file()

    # Reset mock call count
    mock_parser_and_engine["parser"].reset_mock()
    mock_parser_and_engine["match"].reset_mock()

    # Second run: identical file & config -> CACHE_HIT
    res2 = await process_cv_file(
        filename=filename,
        content=cv_bytes,
        candidate_id="user_123",
        cv_id="cv_456",
    )

    assert res2["status"] == "COMPLETED"
    assert res2["original_status"] == "CACHE_HIT"
    assert res2["created_at"] == res1["created_at"]
    assert res2["updated_at"] == res1["updated_at"]
    # Parser and AI scoring MUST NOT be called on CACHE_HIT
    assert mock_parser_and_engine["parser"].call_count == 0
    assert mock_parser_and_engine["match"].await_count == 0

    # Ensure no duplicate JSON files were created
    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) == 1
    assert json_files[0].name == "cv_jane_doe.json"


@pytest.mark.asyncio
async def test_cv_content_change_reprocesses(tmp_path, monkeypatch, mock_parser_and_engine):
    monkeypatch.setattr(settings, "RESULTS_DIR", tmp_path)

    cv_bytes_v1 = b"Original CV content"
    cv_bytes_v2 = b"Updated CV content with new experience"
    filename = "resume.pdf"

    res1 = await process_cv_file(filename=filename, content=cv_bytes_v1, candidate_id="777")
    created_at_v1 = res1["created_at"]
    hash_v1 = res1["cv_hash"]

    # Run with changed content
    res2 = await process_cv_file(filename=filename, content=cv_bytes_v2, candidate_id="777")

    assert res2["status"] == "COMPLETED"
    assert res2["original_status"] == "REPROCESSED"
    assert res2["cv_hash"] != hash_v1
    assert res2["created_at"] == created_at_v1
    assert res2["updated_at"] >= res1["updated_at"]

    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) == 1
    assert json_files[0].name == "cv_resume.json"


@pytest.mark.asyncio
async def test_schema_version_change_reprocesses(tmp_path, monkeypatch, mock_parser_and_engine):
    monkeypatch.setattr(settings, "RESULTS_DIR", tmp_path)

    cv_bytes = b"CV content"
    filename = "resume.pdf"

    res1 = await process_cv_file(filename=filename, content=cv_bytes, candidate_id="888")
    assert res1["status"] == "COMPLETED"
    assert res1["original_status"] == "NEW_CV"

    # Simulate schema version upgrade
    monkeypatch.setattr(settings, "EXTRACTION_SCHEMA_VERSION", "2.0.0")

    res2 = await process_cv_file(filename=filename, content=cv_bytes, candidate_id="888")
    assert res2["status"] == "COMPLETED"
    assert res2["original_status"] == "REPROCESSED"
    assert res2["schema_version"] == "2.0.0"

    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) == 1


@pytest.mark.asyncio
async def test_concurrent_processing_protection(tmp_path, monkeypatch, mock_parser_and_engine):
    monkeypatch.setattr(settings, "RESULTS_DIR", tmp_path)

    cv_bytes = b"Shared CV content for concurrent processing"
    filename = "concurrent_resume.pdf"

    async def run_worker():
        return await process_cv_file(
            filename=filename,
            content=cv_bytes,
            candidate_id="c_concurrent",
            cv_id="cv_concurrent",
        )

    results = await asyncio.gather(*[run_worker() for _ in range(5)])

    assert len(results) == 5
    # Exactly 1 JSON file created
    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) == 1
    assert json_files[0].name == "cv_concurrent_resume.json"
