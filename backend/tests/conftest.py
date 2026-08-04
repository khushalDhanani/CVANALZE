import os
import tempfile
from pathlib import Path

import pytest

from app.core.config import settings
from app.services.embedding_service import EmbeddingService
from app.services.ollama_transport import OllamaTransport


@pytest.fixture(autouse=True)
def isolate_ollama_transport(monkeypatch):
    """Keep every ordinary test offline, serialized, and free of shared clients."""
    OllamaTransport.close()
    live_enabled = os.environ.get("OLLAMA_LIVE_TESTS_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    monkeypatch.setattr(settings, "OLLAMA_LIVE_TESTS_ENABLED", live_enabled)
    monkeypatch.setattr(settings, "OLLAMA_LOCK_FILE", Path(tempfile.gettempdir()) / "cv-analyzer-pytest-ollama.lock")
    monkeypatch.setattr(settings, "OLLAMA_LOCK_TIMEOUT_SECONDS", 1.0)
    yield
    OllamaTransport.close()
    EmbeddingService._failed_models_cache.clear()
