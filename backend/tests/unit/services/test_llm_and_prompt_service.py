from __future__ import annotations

from inspect import getsource

from app.core.config import settings
from app.core.model_registry import ModelRegistry
from app.services.llm_service import OllamaLLMService
from app.services.prompt_service import PromptReadiness, PromptService, ResolvedPrompt


def test_prompt_readiness_named_tuple() -> None:
    readiness = PromptReadiness(ready=True, reason="All prompts verified against schema")
    assert readiness.ready is True
    assert "verified" in readiness.reason


def test_resolved_prompt_named_tuple() -> None:
    resolved = ResolvedPrompt(prompt="Evaluate matching between candidate and vacancies", version_tag="v1.2.0")
    assert resolved.prompt.startswith("Evaluate")
    assert resolved.version_tag == "v1.2.0"


def test_prompt_service_schema_constants() -> None:
    assert PromptService.OPTIMIZED_MATCH_PROMPT_NAME == "optimized_match"
    assert "input_json" in PromptService.OPTIMIZED_MATCH_PLACEHOLDERS
    assert "candidate_profile" in PromptService.OPTIMIZED_MATCH_SCHEMA_FIELDS
    assert "vacancy_id" in PromptService.OPTIMIZED_MATCH_VACANCY_SCHEMA_FIELDS


def test_llm_thinking_capability_uses_runtime_registry(monkeypatch) -> None:
    monkeypatch.setattr(settings, "OLLAMA_THINKING_MODEL_FAMILIES", ["custom-thinker"], raising=False)

    assert ModelRegistry.supports_thinking("custom-thinker:7b") is True
    assert ModelRegistry.supports_thinking("qwen3:8b") is False
    assert OllamaLLMService._supports_thinking("custom-thinker:7b") is True


def test_llm_generation_options_have_no_embedded_numeric_policy() -> None:
    source = getsource(OllamaLLMService)

    assert '"temperature": 0.0' not in source
    assert '"top_p": 0.9' not in source


def test_prompt_service_does_not_embed_hiring_risk_template() -> None:
    source = getsource(PromptService)

    assert "You explain deterministic hiring risks to recruiters." not in source
