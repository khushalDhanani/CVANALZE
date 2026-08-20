from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]


def test_base_compose_has_no_insecure_service_defaults_or_database_ports() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "POSTGRES_PASSWORD:-postgres" not in compose
    assert "redis://redis:6379/0" not in compose
    assert '"5432:5432"' not in compose
    assert '"6380:6379"' not in compose
    assert "http://localhost:8081" not in compose
    assert "POSTGRES_APP_URL: '${POSTGRES_APP_URL:-}'" in compose
    assert "REDIS_URL: '${REDIS_URL:-}'" in compose


def test_local_compose_owns_loopback_service_ports() -> None:
    compose = (REPO_ROOT / "docker-compose.local.yml").read_text(encoding="utf-8")

    assert "POSTGRES_BIND_ADDRESS:-127.0.0.1" in compose
    assert "REDIS_BIND_ADDRESS:-127.0.0.1" in compose


def test_supported_profiles_keep_single_slot_cv_processing() -> None:
    for profile in ("docker-compose.profile-16gb.yml", "docker-compose.profile-32gb.yml"):
        text = (REPO_ROOT / profile).read_text(encoding="utf-8")
        assert "CV_PROCESSING_CONCURRENCY: '1'" in text
        assert "MAX_CONCURRENT_LLM_WORKERS" not in text

    for profile in (".env.profile.8gb", ".env.profile.16gb", ".env.profile.32gb"):
        text = (REPO_ROOT / profile).read_text(encoding="utf-8")
        assert "CV_PROCESSING_CONCURRENCY=1" in text
        assert "MAX_CONCURRENT_LLM_WORKERS" not in text
