from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.cache import embedding_cache_manager, match_result_cache_manager, vacancy_cache_manager
from app.core.config import settings
from app.main import app
from app.services.vector_migration_service import VectorDatabaseMigrationService

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_caches():
    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()
    match_result_cache_manager.clear()
    yield
    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()
    match_result_cache_manager.clear()


def test_vector_db_status_endpoint():
    """
    Verifies GET /api/vector-db/status returns healthy vector DB status.
    """
    with patch.object(VectorDatabaseMigrationService, "get_migration_status", return_value={
        "pgvector_enabled": True,
        "pg_database_connected": True,
        "embedding_model": "nomic-embed-text",
        "candidate_embeddings_count": 42,
        "vacancy_embeddings_count": 10,
        "semantic_retrieval_top_n": 50,
    }):
        resp = client.get("/api/vector-db/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pgvector_enabled"] is True
        assert data["candidate_embeddings_count"] == 42
        assert data["vacancy_embeddings_count"] == 10


def test_vector_db_sync_endpoint():
    """
    Verifies POST /api/vector-db/sync triggers background sync task.
    """
    with patch.object(VectorDatabaseMigrationService, "sync_all_embeddings", return_value={"status": "completed"}):
        resp = client.post("/api/vector-db/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processing"
        assert "started" in data["message"].lower()


def test_incremental_candidate_sync_skips_unchanged():
    """
    Verifies background vector DB sync skips candidates whose embeddings already exist.
    """
    mock_results = [
        {"id": "c1", "filename": "c1.pdf", "markdown": "Python Developer", "cv_hash": "hash1"},
        {"id": "c2", "filename": "c2.pdf", "markdown": "Java Developer", "cv_hash": "hash2"},
    ]

    with patch("app.repositories.result.ResultRepository.list_all_results", return_value=mock_results):
        with patch("app.services.vector_migration_service.get_candidate_embedding", return_value=[0.1] * 768):
            with patch("app.services.embedding_service.EmbeddingService.generate_embedding") as mock_gen:
                metrics = VectorDatabaseMigrationService.sync_candidate_embeddings()
                assert metrics["total"] == 2
                assert metrics["skipped"] == 2
                assert metrics["synced"] == 0
                mock_gen.assert_not_called()


def test_graceful_fallback_when_pg_unavailable():
    """
    Verifies get_migration_status and search operations fall back gracefully when PostgreSQL is disconnected.
    """
    with patch("app.core.database.pg_SessionLocal", None):
        status = VectorDatabaseMigrationService.get_migration_status()
        assert status["pg_database_connected"] is False
        assert status["candidate_embeddings_count"] == 0
