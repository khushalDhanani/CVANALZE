from pathlib import Path

from app.core.config import settings


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_local_compose_inherits_enabled_llm_default_from_base():
    base_compose = (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    local_compose = (REPOSITORY_ROOT / "docker-compose.local.yml").read_text(encoding="utf-8")

    assert "LLM_ENABLED: '${LLM_ENABLED:-true}'" in base_compose
    assert "LLM_ENABLED:" not in local_compose
    assert "EMBEDDING_ENABLED: '${EMBEDDING_ENABLED:-false}'" in local_compose


def test_authoritative_ollama_matching_contract_is_aligned():
    example_env = (REPOSITORY_ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    compose = (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    expected_lines = {
        f"OLLAMA_MODEL={settings.OLLAMA_MODEL}",
        f"EMBEDDING_MODEL={settings.EMBEDDING_MODEL}",
        f"OLLAMA_REQUEST_TIMEOUT={int(settings.OLLAMA_REQUEST_TIMEOUT)}",
        f"OLLAMA_GENERATE_TIMEOUT_SECONDS={int(settings.OLLAMA_GENERATE_TIMEOUT_SECONDS)}",
        f"OLLAMA_MAX_RETRIES={settings.OLLAMA_MAX_RETRIES}",
        f"OLLAMA_OPTIMIZED_NUM_CTX={settings.OLLAMA_OPTIMIZED_NUM_CTX}",
        f"OLLAMA_OPTIMIZED_NUM_PREDICT={settings.OLLAMA_OPTIMIZED_NUM_PREDICT}",
    }
    for line in expected_lines:
        assert line in example_env
    for setting_name in (
        "OLLAMA_MODEL",
        "EMBEDDING_MODEL",
        "OLLAMA_REQUEST_TIMEOUT",
        "OLLAMA_GENERATE_TIMEOUT_SECONDS",
        "OLLAMA_MAX_RETRIES",
        "OLLAMA_OPTIMIZED_NUM_CTX",
        "OLLAMA_OPTIMIZED_NUM_PREDICT",
    ):
        assert f"{setting_name}: '${{{setting_name}" in compose
    assert f"`{settings.OLLAMA_MODEL}`" in readme
    assert f"`{settings.EMBEDDING_MODEL}`" in readme
