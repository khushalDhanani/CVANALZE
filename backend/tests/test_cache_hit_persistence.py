import hashlib
import json

import pytest

from app.core.config import settings
from app.repositories.result import ResultRepository
from app.services.cv_service import get_stable_cv_key, process_cv_file


@pytest.mark.asyncio
async def test_cache_hit_persistence_and_sync(monkeypatch):
    test_filename = "test_cache_hit_sync.pdf"
    test_content = b"Mock PDF Content"
    cv_hash = hashlib.sha256(test_content).hexdigest()
    cv_key = get_stable_cv_key(test_filename)
    result_filename = f"{cv_key}.json"
    result_path = settings.RESULTS_DIR / result_filename

    # Ensure clean state
    if result_path.exists():
        result_path.unlink()

    # 1. Mock a Redis-only state (file missing from disk)
    mock_data = {
        "id": cv_key,
        "filename": test_filename,
        "cv_hash": cv_hash,
        "parser_version": settings.EXTRACTION_PARSER_VERSION,
        "schema_version": settings.EXTRACTION_SCHEMA_VERSION,
        "status": "COMPLETED",
        "progress": 100,
        "markdown": "Mock parsed markdown",
    }

    # Inject directly into ResultRepository read path via monkeypatch
    async def mock_read(*args, **kwargs):
        return mock_data.copy()

    monkeypatch.setattr(
        ResultRepository,
        "read_result_by_filename",
        lambda fn: mock_data.copy() if fn == result_filename else None,
    )

    # Mock embedding generation to not actually call Ollama
    from app.services.embedding_service import EmbeddingService

    monkeypatch.setattr(EmbeddingService, "generate_embedding", lambda text, **kwargs: [0.1] * 768)

    # 2. Trigger process_cv_file
    result = await process_cv_file(test_filename, test_content)

    # 3. Assertions
    assert result["status"] == "COMPLETED"
    assert result["original_status"] == "CACHE_HIT"

    # Verify atomic_save_result successfully recreated the file on disk
    assert result_path.exists(), "Cache hit failed to rebuild the JSON file on disk"

    # Verify the saved content on disk
    saved_data = json.loads(result_path.read_text())
    assert saved_data["status"] == "COMPLETED"
    assert saved_data["original_status"] == "CACHE_HIT"

    # Cleanup
    if result_path.exists():
        result_path.unlink()
