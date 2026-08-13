from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_local_compose_inherits_enabled_llm_default_from_base():
    base_compose = (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    local_compose = (REPOSITORY_ROOT / "docker-compose.local.yml").read_text(encoding="utf-8")

    assert "LLM_ENABLED: '${LLM_ENABLED:-true}'" in base_compose
    assert "LLM_ENABLED:" not in local_compose
    assert "EMBEDDING_ENABLED: '${EMBEDDING_ENABLED:-false}'" in local_compose
