from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from app.core.degradation import DegradationEngine, DegradationMode
from app.core.model_registry import ModelHealthStatus, ModelMetadata, ModelRegistry, ModelType
from app.services.embedding_service import EmbeddingService
from app.services.match_service import MatchService
from app.services.ollama_transport import OllamaError
from app.services.vacancy_prefilter import VacancyPreFilter


@pytest.fixture
def chaos_sample_vacancy() -> dict[str, Any]:
    return {
        "id": "vac-chaos-101",
        "vacancy_id": 101,
        "title": "Software Developer",
        "department": "Engineering",
        "required_skills": ["Python", "FastAPI"],
        "required_skills_are_mandatory": True,
        "min_experience_years": 3.0,
        "job_description": "Building services with Python and FastAPI.",
    }


@pytest.fixture
def chaos_sample_cv() -> str:
    return """
David Miller
Software Developer
Email: david.miller@example.com | Location: Denver, CO

## SUMMARY
Software Developer with 4 years of experience building Python and FastAPI applications.

## SKILLS
Python, FastAPI, Docker, SQL

## WORK EXPERIENCE
Developer | Apex Tech | June 2020 - Present
- Developed Python backend endpoints using FastAPI.

## EDUCATION
B.S. in Computer Science | Colorado State | 2016 - 2020
"""


@pytest.mark.asyncio
async def test_ollama_outage_triggers_deterministic_fallback(
    chaos_sample_cv: str,
    chaos_sample_vacancy: dict[str, Any],
) -> None:
    """Release Gate 3.1: Ollama outage / timeout gracefully falls back to deterministic scoring with typed quality flags."""
    from app.services.ollama_transport import OllamaError
    mock_emb = [0.05] * 768
    with (
        patch.object(EmbeddingService, "generate_embedding", return_value=mock_emb),
        patch("app.services.match_service.settings.LLM_SKIP_COVERAGE_THRESHOLD", 2.0),
        patch("app.services.match_service.OllamaLLMService.run_optimized_match", side_effect=OllamaError(message="Ollama connection refused", operation="generate")),
    ):
        analysis = await MatchService.analyze_single_cv(
            cv_text=chaos_sample_cv,
            job_openings=[chaos_sample_vacancy],
            candidate_experience=4.0,
            document_hash="chaos_doc_hash_001",
            candidate_id="cand_chaos_001",
            cv_embedding=mock_emb,
        )

        assert analysis is not None
        assert analysis.best_match is not None
        assert analysis.best_match.score > 0.0

        # Must flag LLM_UNAVAILABLE_FALLBACK in quality flags
        best = analysis.best_match
        assert "LLM_UNAVAILABLE_FALLBACK" in best.quality_flags


def test_embedding_service_failure_falls_back_to_lexical_retrieval(
    chaos_sample_cv: str,
    chaos_sample_vacancy: dict[str, Any],
) -> None:
    """Release Gate 3.2: Vector embedding failure during prefiltering gracefully falls back to lexical/Stage 0 retrieval."""
    with patch.object(EmbeddingService, "generate_embedding", side_effect=RuntimeError("Vector service offline")):
        shortlist = VacancyPreFilter.filter_vacancies(
            cv_text=chaos_sample_cv,
            openings=[chaos_sample_vacancy],
            candidate_experience=4.0,
            cv_embedding=None,
            top_k=5,
        )

        assert len(shortlist) > 0
        assert shortlist[0]["vacancy_id"] == 101


@pytest.mark.asyncio
async def test_empty_or_scanned_cv_text_safely_rejected() -> None:
    """Release Gate 3.3: Empty or scanned image CVs with no extractable text raise clean ValueError rather than 500 error."""
    with pytest.raises(ValueError, match="CV text content cannot be empty"):
        await MatchService.analyze_single_cv(cv_text="")

    with pytest.raises(ValueError, match="CV document is a scanned image"):
        await MatchService.analyze_single_cv(cv_text="<!-- image --> [scan error]")


def test_model_registry_lifecycle_and_probe_tracking() -> None:
    """Release Gate 3.4: ModelRegistry tracks active models, dimensions, probe health, and latency."""
    ModelRegistry.initialize_defaults()

    active_llm = ModelRegistry.get_active_llm()
    assert active_llm is not None
    assert active_llm.model_type == ModelType.LLM

    active_emb = ModelRegistry.get_active_embedding()
    assert active_emb is not None
    assert active_emb.model_type == ModelType.EMBEDDING
    assert active_emb.dimension == 768

    # Record healthy probe
    ModelRegistry.record_probe(active_llm.name, healthy=True, latency_ms=45.2)
    assert active_llm.health_status == ModelHealthStatus.HEALTHY
    assert active_llm.last_latency_ms == 45.2

    # Record multiple probe failures -> transition to UNREACHABLE
    for _ in range(3):
        ModelRegistry.record_probe(active_llm.name, healthy=False)
    assert active_llm.health_status == ModelHealthStatus.UNREACHABLE

    # Self-heal on next healthy probe
    ModelRegistry.record_probe(active_llm.name, healthy=True, latency_ms=30.0)
    assert active_llm.health_status == ModelHealthStatus.HEALTHY


def test_typed_degradation_engine_reporting() -> None:
    """Release Gate 3.5: DegradationEngine generates typed reports with standardized quality flags."""
    rep_none = DegradationEngine.create_report(DegradationMode.NONE)
    assert rep_none.is_degraded is False
    assert len(rep_none.quality_flags) == 0

    rep_llm = DegradationEngine.create_report(
        DegradationMode.DETERMINISTIC_FALLBACK,
        trigger_reason="Ollama service timed out after 30s",
    )
    assert rep_llm.is_degraded is True
    assert "LLM_UNAVAILABLE_FALLBACK" in rep_llm.quality_flags

    rep_snap = DegradationEngine.create_report(
        DegradationMode.CACHED_VACANCY_SNAPSHOT,
        trigger_reason="MSSQL connection failed",
    )
    assert rep_snap.is_degraded is True
    assert "STALE_VACANCY_SNAPSHOT" in rep_snap.quality_flags
