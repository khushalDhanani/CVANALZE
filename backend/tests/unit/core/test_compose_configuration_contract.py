from __future__ import annotations

import re
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


def test_local_postgres_connection_budget_leaves_operational_headroom() -> None:
    base_compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    local_compose = (REPO_ROOT / "docker-compose.local.yml").read_text(encoding="utf-8")

    def default_value(compose: str, setting: str) -> int:
        match = re.search(rf"{setting}: '\$\{{{setting}:-(\d+)\}}'", compose)
        assert match is not None, f"{setting} must have an explicit Compose default"
        return int(match.group(1))

    pool_size = default_value(local_compose, "POSTGRES_POOL_SIZE")
    max_overflow = default_value(local_compose, "POSTGRES_MAX_OVERFLOW")
    assert pool_size == default_value(base_compose, "POSTGRES_POOL_SIZE")
    assert max_overflow == default_value(base_compose, "POSTGRES_MAX_OVERFLOW")

    max_connections_match = re.search(r'"max_connections=(\d+)"', local_compose)
    assert max_connections_match is not None
    max_connections = int(max_connections_match.group(1))
    runtime_service_count = local_compose.count("<<: *local-backend-environment")
    operational_headroom = 20

    assert runtime_service_count == 4
    assert runtime_service_count * (pool_size + max_overflow) <= max_connections - operational_headroom
