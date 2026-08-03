import hashlib

import fitz
import pytest
from fastapi.testclient import TestClient

from app.core.cache import CacheKey
from app.core.config import settings
from app.core.cv_identity import CVIdentityCollisionError, resolve_cv_identity
from app.main import app
from app.repositories.job import JobRepository
from app.repositories.llm_cache import LLMCacheRepository
from app.repositories.result import ResultRepository
from app.services.match_service import MatchService


def _pdf_bytes() -> bytes:
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Identity collision test")
    content = document.tobytes()
    document.close()
    return content


def test_canonical_identity_prefers_supplied_ids_and_retains_legacy_alias():
    identity = resolve_cv_identity("Resume Final.pdf", candidate_id="candidate-7", cv_id="cv-11")

    assert identity.canonical_key == "cv_candidate_candidate-7_document_cv-11"
    assert identity.legacy_key == "cv_Resume_Final"
    assert identity.strategy == "candidate_and_cv_ids"


def test_same_filename_is_isolated_by_candidate_identity():
    first = resolve_cv_identity("resume.pdf", candidate_id="candidate-1")
    second = resolve_cv_identity("resume.pdf", candidate_id="candidate-2")

    assert first.canonical_key != second.canonical_key
    assert first.legacy_key == second.legacy_key == "cv_resume"


def test_changed_legacy_content_is_reported_as_collision(monkeypatch):
    identity = resolve_cv_identity("resume.pdf")
    existing = {
        "id": identity.canonical_key,
        "filename": "resume.pdf",
        "cv_hash": "existing-hash",
        "candidate_id": None,
        "cv_id": None,
    }
    monkeypatch.setattr(ResultRepository, "read_result_by_filename", lambda _: existing)

    with pytest.raises(CVIdentityCollisionError, match="identity collision"):
        ResultRepository.assert_identity_available(identity, "different-hash")


def test_upload_endpoint_returns_409_for_legacy_identity_collision(monkeypatch, tmp_path):
    existing = {
        "id": "cv_resume",
        "filename": "resume.pdf",
        "cv_hash": "existing-hash",
        "candidate_id": None,
        "cv_id": None,
    }
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(ResultRepository, "read_result_by_filename", lambda _: existing)

    response = TestClient(app).post(
        "/api/match/upload",
        files={"file": ("resume.pdf", _pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 409
    assert list(tmp_path.iterdir()) == []


def test_same_supplied_identity_can_change_content(monkeypatch):
    identity = resolve_cv_identity("resume.pdf", candidate_id="candidate-1", cv_id="cv-1")
    existing = {
        "id": identity.canonical_key,
        "filename": "old-name.pdf",
        "cv_hash": "existing-hash",
        "candidate_id": "candidate-1",
        "cv_id": "cv-1",
    }
    monkeypatch.setattr(ResultRepository, "read_result_by_filename", lambda _: existing)

    ResultRepository.assert_identity_available(identity, "different-hash")


def test_legacy_filename_key_resolves_one_canonical_result(monkeypatch):
    canonical_result = {
        "id": "cv_candidate_candidate-1_document_cv-1",
        "scan_id": "cv_candidate_candidate-1_document_cv-1",
        "legacy_cv_keys": ["cv_resume"],
        "status": "COMPLETED",
    }
    monkeypatch.setattr(ResultRepository, "read_result_by_filename", lambda _: None)
    monkeypatch.setattr(ResultRepository, "find_results_by_scan_id", lambda _: [])
    monkeypatch.setattr(ResultRepository, "list_all_results", lambda: [canonical_result])

    assert ResultRepository.resolve_result("cv_resume") == canonical_result


def test_ambiguous_legacy_filename_key_does_not_choose_a_candidate(monkeypatch):
    results = [
        {
            "id": "cv_candidate_1",
            "legacy_cv_keys": ["cv_resume"],
            "status": "COMPLETED",
        },
        {
            "id": "cv_candidate_2",
            "legacy_cv_keys": ["cv_resume"],
            "status": "COMPLETED",
        },
    ]
    monkeypatch.setattr(ResultRepository, "read_result_by_filename", lambda _: None)
    monkeypatch.setattr(ResultRepository, "find_results_by_scan_id", lambda _: [])
    monkeypatch.setattr(ResultRepository, "list_all_results", lambda: results)

    assert ResultRepository.resolve_result("cv_resume") is None


def test_document_cache_key_isolated_by_content_parser_and_schema_versions():
    base = CacheKey.for_document_extraction("hash-a", "parser-1", "schema-1").to_key()

    assert base != CacheKey.for_document_extraction("hash-b", "parser-1", "schema-1").to_key()
    assert base != CacheKey.for_document_extraction("hash-a", "parser-2", "schema-1").to_key()
    assert base != CacheKey.for_document_extraction("hash-a", "parser-1", "schema-2").to_key()


def test_llm_match_cache_key_includes_every_matching_input():
    base_components = {
        "document_hash": "doc-1",
        "candidate_id": "candidate-1",
        "vacancy_ids": ["vacancy-1"],
        "vacancy_version": "vacancy-version-1",
        "prompt_version": "prompt-1",
        "model_version": "model-1",
        "extraction_version": "extract-1",
        "matching_version": "matching-1",
    }
    base_key = LLMCacheRepository.compute_composite_hash(**base_components)
    changes = {
        "document_hash": "doc-2",
        "candidate_id": "candidate-2",
        "vacancy_ids": ["vacancy-2"],
        "vacancy_version": "vacancy-version-2",
        "prompt_version": "prompt-2",
        "model_version": "model-2",
        "extraction_version": "extract-2",
        "matching_version": "matching-2",
    }

    for component, changed_value in changes.items():
        changed_components = dict(base_components)
        changed_components[component] = changed_value
        assert LLMCacheRepository.compute_composite_hash(**changed_components) != base_key


def test_match_result_cache_key_includes_every_matching_input():
    base_components = {
        "document_hash": "doc-1",
        "candidate_id": "candidate-1",
        "vacancy_version": "vacancy-version-1",
        "vacancy_ids": ["vacancy-1"],
        "prompt_version": "prompt-1",
        "model_version": "model-1",
        "extraction_version": "extract-1",
        "matching_version": "matching-1",
    }
    base_key = CacheKey.for_match_result(**base_components).to_key()
    changes = {
        "document_hash": "doc-2",
        "candidate_id": "candidate-2",
        "vacancy_version": "vacancy-version-2",
        "vacancy_ids": ["vacancy-2"],
        "prompt_version": "prompt-2",
        "model_version": "model-2",
        "extraction_version": "extract-2",
        "matching_version": "matching-2",
    }

    for component, changed_value in changes.items():
        changed_components = dict(base_components)
        changed_components[component] = changed_value
        assert CacheKey.for_match_result(**changed_components).to_key() != base_key


def test_matching_vacancy_version_changes_with_requirement_content():
    original = [{"vacancy_id": 1, "title": "Engineer", "required_skills": ["Python"]}]
    changed = [{"vacancy_id": 1, "title": "Engineer", "required_skills": ["Java"]}]

    assert JobRepository.compute_matching_vacancy_version(original) != JobRepository.compute_matching_vacancy_version(changed)


@pytest.mark.asyncio
async def test_match_service_hashes_raw_text_when_hash_is_missing(monkeypatch):
    captured_components = {}

    class CapturedCacheKey:
        def to_key(self):
            return "captured-match-key"

    def capture_match_key(**components):
        captured_components.update(components)
        return CapturedCacheKey()

    cached_result = MatchService._empty_analysis().model_dump()
    monkeypatch.setattr(CacheKey, "for_match_result", staticmethod(capture_match_key))
    monkeypatch.setattr(
        "app.services.match_service.match_result_cache_manager.get",
        lambda _: cached_result,
    )

    raw_text = "Candidate text with Python experience."
    await MatchService.analyze_single_cv(
        raw_text,
        job_openings=[{"vacancy_id": 1, "title": "Engineer", "department": "Engineering"}],
    )

    assert captured_components["document_hash"] == hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    assert captured_components["model_version"] == settings.OLLAMA_MODEL
    assert captured_components["matching_version"] == settings.MATCHING_VERSION
    assert captured_components["extraction_version"] == (f"{settings.EXTRACTION_PARSER_VERSION}:{settings.EXTRACTION_SCHEMA_VERSION}")
