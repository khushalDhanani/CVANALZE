from __future__ import annotations

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
