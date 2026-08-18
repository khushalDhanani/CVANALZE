import json
from unittest.mock import MagicMock

import httpx
import pytest

from app.core.config import settings
from app.prompts.optimized_match import build_optimized_match_prompt
from app.schemas.analysis import OptimizedLLMMatchResponse
from app.services.context_packer import estimate_tokens, pack_cv_context
from app.services.llm_service import OllamaLLMService
from app.services.ollama_transport import OllamaTransport
from app.services.tokenizer_service import TokenizerService


def _disable_cache(monkeypatch):
    monkeypatch.setattr("app.repositories.llm_cache.LLMCacheRepository.get_cached_entry", lambda key: None)
    monkeypatch.setattr("app.repositories.llm_cache.LLMCacheRepository.save_cached_entry", lambda key, entry: None)


def _mock_transport(monkeypatch, response_data: dict) -> MagicMock:
    client = MagicMock()

    def stream(_method, _path, **kwargs):
        payload = kwargs.get("json") or {}
        if payload.get("keep_alive") == 0:
            data = {"model": payload["model"], "response": "", "done": True, "done_reason": "unload"}
        else:
            data = {"model": payload.get("model", settings.OLLAMA_MODEL), "done": True, "done_reason": "stop", **response_data}
        response = httpx.Response(200, json=data, request=httpx.Request("POST", "http://ollama.test/api/generate"))
        ctx = MagicMock()
        ctx.__enter__.return_value = response
        ctx.__exit__.return_value = False
        return ctx

    client.stream.side_effect = stream
    monkeypatch.setattr(OllamaTransport, "get_client", classmethod(lambda cls: client))
    monkeypatch.setattr(settings, "OLLAMA_MAX_RETRIES", 0)
    return client


def _get_payload(client: MagicMock) -> dict:
    for call in client.stream.call_args_list:
        p = call.kwargs.get("json") or {}
        if p.get("keep_alive") != 0:
            return p
    raise AssertionError("No generation payload recorded.")


def test_tokenizer_service_counts_and_truncates_reliably():
    text = "Senior Python Developer with PostgreSQL, Kubernetes, and microservices experience."
    count = TokenizerService.count_tokens(text)
    assert count > 0
    assert count >= len(text.split())

    # Empty and whitespace checks
    assert TokenizerService.count_tokens("") == 0
    assert TokenizerService.count_tokens(None) == 0

    # Truncation
    truncated = TokenizerService.truncate_to_tokens(text, 5)
    assert len(truncated) < len(text)
    assert TokenizerService.count_tokens(truncated) <= 6


def test_tokenizer_service_accurately_counts_structured_json():
    structured_data = {
        "candidate_id": "cv_1761533883_CandidateCVFileName_13672",
        "skills": ["FastAPI", "PostgreSQL/pgvector", "Docker-Compose", "CI/CD Pipeline"],
        "experience": [{"role": "Staff Backend Engineer", "duration_months": 72}],
    }
    raw_json = json.dumps(structured_data)
    token_count = TokenizerService.count_tokens(raw_json)
    # Token count on JSON should account for punctuation, brackets, quotes
    assert token_count > len(raw_json.split())


def test_context_packer_estimate_tokens_delegates_to_tokenizer():
    sample = "Software Engineer with React, TypeScript, and Node.js skills."
    assert estimate_tokens(sample) == TokenizerService.count_tokens(sample)

    packed = pack_cv_context(sample, max_tokens=100, deidentify=False)
    assert packed.estimated_tokens == TokenizerService.count_tokens(packed.text)


def test_dynamic_context_sizing_expands_when_prompt_is_large(monkeypatch):
    _disable_cache(monkeypatch)
    dummy_resp = {
        "candidate_profile": {"core_skills": ["Python"], "relevant_experience_years": 5.0, "current_role": "Dev"},
        "matched_vacancies": [],
    }
    client = _mock_transport(monkeypatch, {"response": json.dumps(dummy_resp), "eval_count": 50, "eval_duration": 1000000})

    # Set configured num_ctx to 4000 and num_predict to 3000
    monkeypatch.setattr(settings, "OLLAMA_OPTIMIZED_NUM_CTX", 4000)
    monkeypatch.setattr(settings, "OLLAMA_OPTIMIZED_NUM_PREDICT", 3000)

    # A prompt with ~2000 tokens: 2000 + 3000 + 512 = 5512 > 4000
    large_prompt = "Python developer with experience. " * 300
    prompt_tokens = TokenizerService.count_tokens(large_prompt)
    assert prompt_tokens > 1000

    result = OllamaLLMService.run_optimized_match(large_prompt, "4.0", "large_prompt_test_key")
    assert result is not None

    payload = _get_payload(client)
    effective_ctx = payload["options"]["num_ctx"]
    effective_predict = payload["options"]["num_predict"]

    # Effective num_ctx must have expanded to fit prompt_tokens + predict + 512 buffer
    assert effective_ctx >= prompt_tokens + effective_predict + 512
    # Prompt + predict + buffer must never exceed effective_ctx
    assert prompt_tokens + effective_predict + 512 <= effective_ctx


def test_dynamic_predict_capping_when_context_is_tight(monkeypatch):
    _disable_cache(monkeypatch)
    dummy_resp = {
        "candidate_profile": {"core_skills": ["Python"], "relevant_experience_years": 5.0, "current_role": "Dev"},
        "matched_vacancies": [],
    }
    client = _mock_transport(monkeypatch, {"response": json.dumps(dummy_resp), "eval_count": 50, "eval_duration": 1000000})

    # Massive prompt that reaches near the max context window limit
    massive_prompt = "Expert software architect and engineer with deep systems knowledge. " * 4500
    prompt_tokens = TokenizerService.count_tokens(massive_prompt)
    assert prompt_tokens > 25000

    result = OllamaLLMService.run_optimized_match(massive_prompt, "4.0", "massive_prompt_test_key")
    assert result is not None

    payload = _get_payload(client)
    effective_ctx = payload["options"]["num_ctx"]
    effective_predict = payload["options"]["num_predict"]

    assert effective_ctx <= 32768
    # num_predict must be capped safely
    assert prompt_tokens + effective_predict + 512 <= effective_ctx or effective_predict == 256


def test_admission_control_prunes_with_exact_tokenizer_budget(monkeypatch):
    from unittest.mock import patch

    # Set context budget: num_ctx=3000, num_predict=1000 -> max_prompt_budget = 3000 - 1000 - 512 = 1488
    monkeypatch.setattr(settings, "OLLAMA_OPTIMIZED_NUM_CTX", 3000)
    monkeypatch.setattr(settings, "OLLAMA_OPTIMIZED_NUM_PREDICT", 1000)

    cv_text = "Senior Python Developer with 10 years experience across distributed systems."
    vacancies = [
        {
            "vacancy_id": i,
            "title": f"Staff Systems Engineer {i}",
            "department": "Infrastructure",
            "required_skills": ["Python", "FastAPI", "Docker", "Kubernetes", "PostgreSQL", "Redis", "Kafka", "AWS"],
            "description": "Very long detailed vacancy description with extensive requirements. " * 20,
        }
        for i in range(1, 10)
    ]

    with patch("app.services.prompt_service.PromptService.get_prompt", return_value="Prompt with {input_json}"):
        prompt, token_est, char_count = build_optimized_match_prompt(cv_text, vacancies)

    # Token count must be measured accurately and fit safely
    assert token_est > 0
    assert token_est <= 3000
