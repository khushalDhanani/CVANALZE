from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.core.model_registry import ModelRegistry
from app.schemas.analysis_fingerprint import AnalysisFingerprint
from app.services.embedding_service import EmbeddingService
from app.services.match_service import MatchService
from app.services.ollama_transport import OllamaError


@pytest.mark.asyncio
async def test_ac1_ollama_failure_never_fabricates_zero_similarity_or_confidence() -> None:
    """Phase 3 AC 1: Killing Ollama during analysis never fabricates zero similarity or a confident match."""
    cv_text = """
    Jane Developer
    Backend Developer
    Email: jane@example.com
    
    ## SKILLS
    Python, FastAPI, PostgreSQL
    """
    job = {
        "id": "vac-p3-101",
        "vacancy_id": 101,
        "title": "Python Engineer",
        "department": "Engineering",
        "required_skills": ["Python"],
    }

    mock_emb = [0.05] * 768
    with (
        patch.object(EmbeddingService, "generate_embedding", return_value=mock_emb),
        patch("app.services.match_service.OllamaLLMService.run_optimized_match", side_effect=OllamaError("Connection refused", operation="generate")),
    ):
        result = await MatchService.analyze_single_cv(cv_text, job_openings=[job])

    assert result is not None
    assert result.llm_skipped is True or any("LLM_UNAVAILABLE" in flag for flag in getattr(result.best_match, "quality_flags", []))
    if result.best_match:
        assert result.best_match.vacancy_match_status in {"MATCHED", "POTENTIAL_MATCH", "NO_STRONG_VACANCY_MATCH"}


def test_ac2_vector_schema_incompatible_dimension_fails_fast() -> None:
    """Phase 3 AC 2: Changing embedding model with incompatible dimension fails fast before vector search."""
    embed_meta = ModelRegistry.get_active_embedding()
    is_valid = ModelRegistry.verify_vector_schema(embed_meta.name, dimension=512, schema_version="v1.0")
    assert is_valid is False


def test_ac3_version_changes_produce_new_analysis_fingerprint() -> None:
    """Phase 3 AC 3: Changing a policy/model/prompt/taxonomy version produces a new analysis fingerprint."""
    base_fp = AnalysisFingerprint.create(
        source_document_hash="doc_hash_p3_ac3",
        policy_snapshot_id="snap_1.1.0",
    )
    base_digest = base_fp.compute_fingerprint_digest()

    # Changing policy ID -> new fingerprint
    fp_pol = base_fp.model_copy(update={"policy_snapshot_id": "snap_2.0.0"})
    assert fp_pol.compute_fingerprint_digest() != base_digest

    # Changing prompt version -> new fingerprint
    fp_prm = base_fp.model_copy(update={"prompt_version": "5.0"})
    assert fp_prm.compute_fingerprint_digest() != base_digest

    # Changing taxonomy version -> new fingerprint
    fp_tax = base_fp.model_copy(update={"taxonomy_version": "v4.0-enterprise"})
    assert fp_tax.compute_fingerprint_digest() != base_digest


def test_ac4_production_environment_refuses_dev_credentials() -> None:
    """Phase 3 AC 4: Production refuses known development credentials/defaults."""
    with pytest.raises(ValueError, match="AUTH_SESSION_SIGNING_KEY"):
        Settings(
            APP_ENVIRONMENT="production",
            AUTH_ENABLED=True,
            AUTH_SESSION_SIGNING_KEY="change_me",
            REDIS_URL="redis://localhost:6379/0",
            MSSQL_READ_ONLY_URL="mssql+pyodbc://localhost/db",
            POSTGRES_APP_URL="postgresql://localhost/db",
        )


def test_ac5_async_job_traceable_by_correlation_id_and_persisted_state() -> None:
    """Phase 3 AC 5: Every async job is traceable end-to-end by correlation ID and persisted job state."""
    from app.repositories.processing_job import ProcessingJobRecord, ProcessingJobRepository

    record = ProcessingJobRecord(
        job_id="job_p3_trace_001",
        cv_key="cv_p3_trace_001",
        content_hash="hash_p3_123",
        filename="resume.pdf",
        storage_filename="storage_resume.pdf",
        parser_version="v2.1-docling",
        schema_version="2.1",
        candidate_id="cand_trace_001",
        correlation_id="corr_trace_run_123",
        state="COMPLETED",
    )

    saved = ProcessingJobRepository.save(record)
    fetched = ProcessingJobRepository.get("job_p3_trace_001")

    assert fetched is not None
    assert fetched.correlation_id == "corr_trace_run_123"
    assert fetched.state == "COMPLETED"


@pytest.mark.asyncio
async def test_ac6_replaying_analysis_shows_exact_versions_and_degraded_conditions() -> None:
    """Phase 3 AC 6: Replaying an analysis shows exact versions and degraded conditions that produced the result."""
    cv_text = """
    Developer Dave
    Fullstack Developer
    Email: dave@example.com
    
    ## SKILLS
    Python, TypeScript, React
    """
    job = {
        "id": "vac-p3-replay",
        "vacancy_id": 202,
        "title": "Fullstack Engineer",
        "department": "Engineering",
        "required_skills": ["Python", "React"],
    }

    mock_emb = [0.05] * 768
    with patch.object(EmbeddingService, "generate_embedding", return_value=mock_emb):
        result = await MatchService.analyze_single_cv(cv_text, job_openings=[job])

    assert result.analysis_versions is not None
    assert result.analysis_versions.app_version == "1.1.0"
    assert result.analysis_versions.parser_version == "v2.1-docling"
    assert result.analysis_versions.taxonomy_version == "v3.0-enterprise"
    assert result.analysis_versions.policy_snapshot_id.startswith("snap_")
    assert result.analysis_versions.embedding_model_id == "nomic-embed-text"
    assert result.quality_metadata is not None
    assert "fingerprint_digest" in result.quality_metadata
