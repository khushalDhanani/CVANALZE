from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import inspect, text

from app.core.cache import embedding_cache_manager
from app.core.config import settings
from app.core.database import postgres_app_engine, PostgresAppSession
from app.models.pg import CandidateEmbedding, VacancyEmbedding
from app.services.embedding_service import (
    EmbeddingCacheStatus,
    EmbeddingDatabaseConnectionError,
    EmbeddingSchemaError,
    get_candidate_embedding,
    get_candidate_embedding_with_status,
    get_vacancy_embedding_with_status,
    save_candidate_embedding,
    save_vacancy_embedding,
)



@pytest.fixture(autouse=True)
def clear_embedding_cache():
    embedding_cache_manager.clear()
    yield
    embedding_cache_manager.clear()


def test_fresh_start_missing_row_returns_cache_miss_and_evicts_orphan_cache():
    """
    Verifies that when PostgreSQL has no row for cv_key:
    - Any orphan L2/L3 cache entry is evicted.
    - get_candidate_embedding_with_status returns (None, CACHE_MISS).
    - No error is raised.
    """
    cv_key = "test_fresh_start_cand_001"
    cache_key = f"{settings.EMBEDDING_MODEL}:{cv_key}"

    # Pre-populate orphan L2/L3 cache
    embedding_cache_manager.set(cache_key, [0.1] * 768)
    assert embedding_cache_manager.get(cache_key) is not None

    # Ensure PG row does not exist
    if PostgresAppSession:
        with PostgresAppSession() as session:
            session.query(CandidateEmbedding).filter(CandidateEmbedding.cv_key == cv_key).delete()
            session.commit()

    # Perform lookup
    vec, status = get_candidate_embedding_with_status(cv_key)

    assert status == EmbeddingCacheStatus.CACHE_MISS
    assert vec is None
    # Orphan cache must be evicted
    assert embedding_cache_manager.get(cache_key) is None


def test_save_candidate_embedding_persists_metadata_and_populates_cache():
    """
    Verifies FIRST RUN lifecycle:
    1. MISS → Generate → Save PG (upsert + commit) → Populate cache.
    2. SECOND RUN: FRESH + same content_hash → CACHE_HIT.
    """
    cv_key = "test_save_cand_002"
    fake_embedding = [0.123] * 768
    content_hash = "abc123hash"
    source_snapshot = '{"filename": "test.pdf"}'
    watermark = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Clean state
    vec, status = get_candidate_embedding_with_status(cv_key, current_content_hash=content_hash)
    assert status == EmbeddingCacheStatus.CACHE_MISS
    assert vec is None

    # 2. Save candidate embedding
    saved = save_candidate_embedding(
        cv_key=cv_key,
        embedding=fake_embedding,
        content_hash=content_hash,
        source_snapshot=source_snapshot,
        source_watermark=watermark,
        freshness_status="FRESH",
    )
    assert saved is True

    # Verify PostgreSQL row content
    with PostgresAppSession() as session:
        rec = session.query(CandidateEmbedding).filter(CandidateEmbedding.cv_key == cv_key).first()
        assert rec is not None
        assert rec.content_hash == content_hash
        assert rec.source_snapshot == source_snapshot
        assert rec.freshness_status == "FRESH"
        assert rec.embedding is not None

    # 3. Second run lookup → CACHE_HIT
    vec_hit, status_hit = get_candidate_embedding_with_status(cv_key, current_content_hash=content_hash)
    assert status_hit == EmbeddingCacheStatus.CACHE_HIT
    assert vec_hit is not None
    assert len(vec_hit) == 768
    assert abs(vec_hit[0] - 0.123) < 1e-4

    # Simple wrapper check
    cached_vec = get_candidate_embedding(cv_key)
    assert cached_vec is not None

    # Cleanup
    with PostgresAppSession() as session:
        session.query(CandidateEmbedding).filter(CandidateEmbedding.cv_key == cv_key).delete()
        session.commit()


def test_source_content_hash_change_triggers_stale_cache_and_evicts():
    """
    Verifies CV CHANGED lifecycle:
    PG row exists + content_hash changed → STALE_CACHE → evict cache → returns None.
    """
    cv_key = "test_stale_cand_003"
    fake_embedding = [0.456] * 768
    old_hash = "old_hash_v1"
    new_hash = "new_hash_v2"

    save_candidate_embedding(
        cv_key=cv_key,
        embedding=fake_embedding,
        content_hash=old_hash,
        freshness_status="FRESH",
    )

    # Querying with old hash → CACHE_HIT
    vec, status = get_candidate_embedding_with_status(cv_key, current_content_hash=old_hash)
    assert status == EmbeddingCacheStatus.CACHE_HIT
    assert vec is not None

    # Querying with changed content hash → STALE_CACHE
    vec_stale, status_stale = get_candidate_embedding_with_status(cv_key, current_content_hash=new_hash)
    assert status_stale == EmbeddingCacheStatus.STALE_CACHE
    assert vec_stale is None

    # Cache key must be evicted
    cache_key = f"{settings.EMBEDDING_MODEL}:{cv_key}"
    assert embedding_cache_manager.get(cache_key) is None

    # Cleanup
    with PostgresAppSession() as session:
        session.query(CandidateEmbedding).filter(CandidateEmbedding.cv_key == cv_key).delete()
        session.commit()


def test_db_write_failure_rollback_does_not_populate_cache():
    """
    Verifies that on save_candidate_embedding failure:
    - rollback() is called.
    - Exception is re-raised.
    - L2/L3 cache is NOT populated.
    """
    cv_key = "test_failed_save_004"
    cache_key = f"{settings.EMBEDDING_MODEL}:{cv_key}"

    with patch("app.core.database.PostgresAppSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.execute.side_effect = RuntimeError("DB write error")

        with pytest.raises(RuntimeError, match="DB write error"):
            save_candidate_embedding(
                cv_key=cv_key,
                embedding=[0.999] * 768,
                content_hash="fail_hash",
            )

        mock_session.rollback.assert_called_once()
        assert embedding_cache_manager.get(cache_key) is None


def test_missing_column_raises_embedding_schema_error():
    """
    Verifies BROKEN MIGRATION behavior:
    SQLSTATE 42703 (UndefinedColumn) → raises EmbeddingSchemaError (DB_SCHEMA_ERROR) → NO cache fallback.
    """
    cv_key = "test_schema_err_005"
    cache_key = f"{settings.EMBEDDING_MODEL}:{cv_key}"

    # Pre-populate cache to ensure cache fallback does NOT occur
    embedding_cache_manager.set(cache_key, [0.5] * 768)

    mock_exc = Exception("column candidate_embeddings.source_snapshot does not exist")
    mock_orig = MagicMock()
    mock_orig.pgcode = "42703"
    setattr(mock_exc, "orig", mock_orig)

    with patch("app.core.database.PostgresAppSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.query.side_effect = mock_exc

        with pytest.raises(EmbeddingSchemaError, match="42703"):
            get_candidate_embedding_with_status(cv_key)


def test_dual_table_schema_verification():
    """
    Verifies after migration 017, all model-defined columns exist in PostgreSQL
    for both candidate_embeddings and vacancy_embeddings tables.
    """
    inspector = inspect(postgres_app_engine)
    cand_cols = {c["name"] for c in inspector.get_columns("candidate_embeddings")}
    vac_cols = {c["name"] for c in inspector.get_columns("vacancy_embeddings")}

    required_columns = {"source_snapshot", "source_watermark", "freshness_status", "content_hash", "embedding", "embedding_model_version", "updated_at"}

    assert required_columns.issubset(cand_cols), f"candidate_embeddings missing: {required_columns - cand_cols}"
    assert required_columns.issubset(vac_cols), f"vacancy_embeddings missing: {required_columns - vac_cols}"


def test_vacancy_embedding_cache_miss_hit_and_stale_flow():
    """
    Verifies vacancy embedding lifecycle:
    MISS → Save PG + Commit → CACHE_HIT → Content change → STALE_CACHE → evict cache.
    """
    vacancy_id = 999999
    fake_vec = [0.888] * 768
    old_hash = "vac_hash_old"
    new_hash = "vac_hash_new"

    # Clean PG state for test vacancy
    if PostgresAppSession:
        with PostgresAppSession() as session:
            session.query(VacancyEmbedding).filter(VacancyEmbedding.vacancy_id == vacancy_id).delete()
            session.commit()

    # 1. First lookup → CACHE_MISS
    vec, hash_val, status = get_vacancy_embedding_with_status(vacancy_id, current_content_hash=old_hash)
    assert status == EmbeddingCacheStatus.CACHE_MISS
    assert vec is None

    # 2. Save vacancy embedding
    saved = save_vacancy_embedding(
        vacancy_id=vacancy_id,
        embedding=fake_vec,
        content_hash=old_hash,
        freshness_status="FRESH",
    )
    assert saved is True

    # 3. Second lookup → CACHE_HIT
    vec_hit, hash_hit, status_hit = get_vacancy_embedding_with_status(vacancy_id, current_content_hash=old_hash)
    assert status_hit == EmbeddingCacheStatus.CACHE_HIT
    assert vec_hit is not None
    assert hash_hit == old_hash

    # 4. Content change → STALE_CACHE
    vec_stale, hash_stale, status_stale = get_vacancy_embedding_with_status(vacancy_id, current_content_hash=new_hash)
    assert status_stale == EmbeddingCacheStatus.STALE_CACHE
    assert vec_stale is None

    # Cleanup
    if PostgresAppSession:
        with PostgresAppSession() as session:
            session.query(VacancyEmbedding).filter(VacancyEmbedding.vacancy_id == vacancy_id).delete()
            session.commit()

