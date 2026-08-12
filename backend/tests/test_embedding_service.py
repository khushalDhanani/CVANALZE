from unittest.mock import patch

import pytest

from app.core.cache import embedding_cache_manager
from app.services.embedding_service import EmbeddingService


@pytest.fixture(autouse=True)
def reset_cache_and_metrics():
    embedding_cache_manager.clear()
    EmbeddingService.reset_metrics()
    yield
    embedding_cache_manager.clear()
    EmbeddingService.reset_metrics()


def test_embedding_metrics_and_caching():
    mock_vector = [0.1, 0.2, 0.3, 0.4]

    with patch(
        "app.services.embedding_service.EmbeddingService._call_ollama_embed",
        return_value=mock_vector,
    ) as mock_call:
        # Initial request: Cache MISS
        emb1 = EmbeddingService.generate_embedding("John Doe CV text", identifier="cv_101")
        assert emb1 == mock_vector
        assert mock_call.call_count == 1

        metrics = EmbeddingService.get_metrics()
        assert metrics["total_requests"] == 1
        assert metrics["cache_hits"] == 0
        assert metrics["cache_misses"] == 1
        assert metrics["cache_hit_rate_pct"] == 0.0
        assert metrics["last_processing_time_ms"] >= 0.0

        # Second request with same text: Cache HIT
        emb2 = EmbeddingService.generate_embedding("John Doe CV text", identifier="cv_101")
        assert emb2 == mock_vector
        assert mock_call.call_count == 1  # No additional Ollama call

        metrics2 = EmbeddingService.get_metrics()
        assert metrics2["total_requests"] == 2
        assert metrics2["cache_hits"] == 1
        assert metrics2["cache_misses"] == 1
        assert metrics2["cache_hit_rate_pct"] == 50.0

        # Third request looking up by content hash: Cache HIT via primary key
        emb3 = EmbeddingService.generate_embedding("John Doe CV text")
        assert emb3 == mock_vector
        assert mock_call.call_count == 1

        metrics3 = EmbeddingService.get_metrics()
        assert metrics3["total_requests"] == 3
        assert metrics3["cache_hits"] == 2
        assert metrics3["cache_misses"] == 1


def test_embedding_non_blocking_on_failure():
    with patch(
        "app.services.embedding_service.EmbeddingService._call_ollama_embed",
        side_effect=RuntimeError("Ollama service down"),
    ):
        emb = EmbeddingService.generate_embedding("CV text on server down", identifier="cv_error_1")
        assert emb is None  # Does not raise, returns None gracefully

        metrics = EmbeddingService.get_metrics()
        assert metrics["total_requests"] == 1
        assert metrics["cache_misses"] == 1


def test_embedding_version_tracking():
    mock_vector_v1 = [0.1, 0.1, 0.1]
    mock_vector_v2 = [0.9, 0.9, 0.9]

    def mock_embed(model, text):
        if model == "model-v1":
            return mock_vector_v1
        return mock_vector_v2

    with patch(
        "app.services.embedding_service.EmbeddingService._call_ollama_embed",
        side_effect=mock_embed,
    ):
        emb_v1 = EmbeddingService.generate_embedding("Same text", model_version="model-v1")
        emb_v2 = EmbeddingService.generate_embedding("Same text", model_version="model-v2")

        assert emb_v1 == mock_vector_v1
        assert emb_v2 == mock_vector_v2

        metrics = EmbeddingService.get_metrics()
        assert metrics["total_requests"] == 2
        assert metrics["cache_misses"] == 2


@pytest.mark.asyncio
async def test_single_embedding_in_cv_pipeline():
    from app.services.match_service import MatchService

    mock_emb = [0.5, 0.5, 0.5]
    openings = [
        {
            "id": "job1",
            "title": "Developer",
            "department": "IT",
            "required_skills": ["Python"],
        }
    ]

    with (
        patch(
            "app.services.embedding_service.EmbeddingService.generate_embedding",
            return_value=mock_emb,
        ) as mock_gen,
        patch("app.repositories.job.JobRepository.get_all_jobs", return_value=openings),
    ):
        analysis = await MatchService.analyze_single_cv(
            cv_text="Python developer with 5 years experience in web APIs",
            cv_embedding=mock_emb,
        )
        assert analysis is not None
        # VacancyPreFilter reused passed cv_embedding without calling generate_embedding again
        assert mock_gen.call_count == 0


def test_reset_metrics():
    with patch(
        "app.services.embedding_service.EmbeddingService._call_ollama_embed",
        return_value=[0.1],
    ):
        EmbeddingService.generate_embedding("Sample text")
        assert EmbeddingService.get_metrics()["total_requests"] == 1

        EmbeddingService.reset_metrics()
        reset = EmbeddingService.get_metrics()
        assert reset["total_requests"] == 0
        assert reset["cache_hits"] == 0
        assert reset["cache_misses"] == 0
        assert reset["last_processing_time_ms"] == 0.0
