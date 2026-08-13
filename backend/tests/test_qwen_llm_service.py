import json
from unittest.mock import MagicMock

import httpx

from app.core.config import settings
from app.schemas.analysis import (
    DynamicMappingResponse,
    OptimizedLLMMatchResponse,
    QwenCVAnalysis,
)
from app.schemas.profile import DynamicCandidateProfile
from app.services.llm_service import OllamaLLMService
from app.services.ollama_transport import OllamaTransport


def _disable_llm_cache(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.repositories.llm_cache.LLMCacheRepository.get_cached_entry",
        lambda key: None,
    )
    monkeypatch.setattr(
        "app.repositories.llm_cache.LLMCacheRepository.save_cached_entry",
        lambda key, entry: None,
    )


def _mock_transport_client(monkeypatch, response_data: dict) -> MagicMock:
    client = MagicMock()

    def stream(_method, _path, **kwargs):
        payload = kwargs.get("json") or {}
        if payload.get("keep_alive") == 0:
            data = {
                "model": payload["model"],
                "response": "",
                "done": True,
                "done_reason": "unload",
            }
        else:
            data = {
                "model": payload.get("model", settings.OLLAMA_MODEL),
                "done": True,
                "done_reason": "stop",
                **response_data,
            }
        response = httpx.Response(
            200,
            json=data,
            request=httpx.Request("POST", "http://ollama.test/api/generate"),
        )
        context = MagicMock()
        context.__enter__.return_value = response
        context.__exit__.return_value = False
        return context

    client.stream.side_effect = stream
    monkeypatch.setattr(OllamaTransport, "get_client", classmethod(lambda cls: client))
    monkeypatch.setattr(settings, "OLLAMA_MAX_RETRIES", 0)
    return client


def _generation_payload(client: MagicMock) -> dict:
    for request_call in client.stream.call_args_list:
        payload = request_call.kwargs.get("json") or {}
        if payload.get("keep_alive") != 0:
            return payload
    raise AssertionError("No generation request was recorded.")


def test_ollama_default_model_is_llama3_2_3b():
    assert settings.OLLAMA_MODEL == "llama3.2:3b"


def test_extract_candidate_profile_payload_and_prompt(monkeypatch):
    _disable_llm_cache(monkeypatch)
    dummy_profile = {
        "education_domains": ["Computer Science"],
        "professional_domains": ["Software Development"],
        "current_domain": "Software Development",
        "current_role": "Python Developer",
        "previous_roles": [],
        "career_transitions": [],
        "core_skills": ["Python", "FastAPI"],
        "relevant_experience_years": 4.0,
        "timeline": [],
        "confidence": "HIGH",
        "evidence_notes": "Extracted from CV",
    }
    client = _mock_transport_client(
        monkeypatch,
        {
            "response": json.dumps(dummy_profile),
            "eval_count": 100,
            "eval_duration": 1_000_000_000,
        },
    )

    result = OllamaLLMService.extract_candidate_profile(
        prompt="Extract candidate CV details",
        prompt_version="1.0",
        cache_key="test_extraction_cache_key",
    )

    assert isinstance(result, DynamicCandidateProfile)
    payload = _generation_payload(client)
    assert payload["model"] == "llama3.2:3b"
    assert payload["prompt"] == "Extract candidate CV details"
    assert "think" not in payload
    assert payload["format"] == DynamicCandidateProfile.model_json_schema()
    assert payload["options"]["temperature"] == 0.0
    assert payload["keep_alive"] == settings.OLLAMA_KEEP_ALIVE


def test_call_qwen_scoring_payload_and_prompt(monkeypatch):
    _disable_llm_cache(monkeypatch)
    dummy_analysis = {
        "skill_matches": ["Python"],
        "inferred_skills": ["FastAPI"],
        "missing_critical": [],
        "semantic_reason": "Good match",
    }
    client = _mock_transport_client(
        monkeypatch,
        {
            "response": json.dumps(dummy_analysis),
            "eval_count": 100,
            "eval_duration": 1_000_000_000,
        },
    )

    result = OllamaLLMService.call_qwen(
        prompt="Score CV fit for Python Developer",
        prompt_version="1.0",
        cache_key="test_call_qwen_cache_key",
    )

    assert isinstance(result, QwenCVAnalysis)
    payload = _generation_payload(client)
    assert payload["model"] == "llama3.2:3b"
    assert payload["prompt"] == "Score CV fit for Python Developer"
    assert "think" not in payload
    assert payload["format"] == QwenCVAnalysis.model_json_schema()
    assert payload["options"]["temperature"] == 0.0


def test_call_qwen_dynamic_scoring_payload_and_prompt(monkeypatch):
    _disable_llm_cache(monkeypatch)
    dummy_mapping = {
        "matched_vacancies": [
            {
                "vacancy_id": 101,
                "semantic_reason": "Matched backend skill set",
                "inferred_skills": ["Docker"],
            }
        ]
    }
    client = _mock_transport_client(
        monkeypatch,
        {
            "response": json.dumps(dummy_mapping),
            "eval_count": 100,
            "eval_duration": 1_000_000_000,
        },
    )

    result = OllamaLLMService.call_qwen_dynamic(
        prompt="Score candidate dynamic mapping",
        prompt_version="2.0",
        cache_key="test_dynamic_cache_key",
    )

    assert isinstance(result, DynamicMappingResponse)
    payload = _generation_payload(client)
    assert payload["model"] == "llama3.2:3b"
    assert payload["prompt"] == "Score candidate dynamic mapping"
    assert "think" not in payload
    assert payload["format"] == DynamicMappingResponse.model_json_schema()
    assert payload["options"]["temperature"] == 0.0


def test_run_optimized_match_scoring_payload_and_prompt(monkeypatch, caplog):
    caplog.set_level("INFO", logger="cv_analyzer")
    _disable_llm_cache(monkeypatch)
    monkeypatch.setattr(settings, "OLLAMA_OPTIMIZED_NUM_CTX", 8192)
    monkeypatch.setattr(settings, "OLLAMA_OPTIMIZED_NUM_PREDICT", 3072)
    dummy_optimized = {
        "candidate_profile": {
            "core_skills": ["Python"],
            "inferred_skills": ["SQL"],
            "relevant_experience_years": 5.0,
            "current_role": "Python Developer",
        },
        "matched_vacancies": [
            {
                "vacancy_id": 101,
                "semantic_reason": "Direct experience with Python",
                "top_strength": "The CV explicitly documents Python experience, directly matching the vacancy's Python requirement. This is the strongest role-specific evidence.",
                "main_concern": "The CV does not describe the production scale expected by the vacancy. Recruiters should verify deployment ownership rather than infer it.",
                "ai_match_explanation": "The high score reflects the direct Python overlap between the CV and vacancy. Missing production-scale evidence limits complete confidence.",
                "semantic_fit_score": 90.0,
            }
        ],
        "active_vacancy_summary": "Python vacancy evaluated.",
        "ai_career_summary": "Backend engineering profile.",
    }
    client = _mock_transport_client(
        monkeypatch,
        {
            "response": json.dumps(dummy_optimized),
            "eval_count": 120,
            "eval_duration": 1_500_000_000,
        },
    )

    result = OllamaLLMService.run_optimized_match(
        prompt="Perform optimized match evaluation",
        prompt_version="3.0",
        cache_key="test_optimized_match_cache_key",
    )

    assert isinstance(result, OptimizedLLMMatchResponse)
    payload = _generation_payload(client)
    assert payload["model"] == "llama3.2:3b"
    assert payload["prompt"] == "Perform optimized match evaluation"
    assert "think" not in payload
    assert payload["format"] == OptimizedLLMMatchResponse.model_json_schema()
    assert payload["options"]["temperature"] == 0.0
    assert payload["options"]["num_ctx"] == 8192
    assert payload["options"]["num_predict"] == 3072
    assert "response_chars=" in caplog.text
    assert "num_predict=3072" in caplog.text
    assert "num_ctx=8192" in caplog.text


def test_thinking_model_retains_native_think_parameter(monkeypatch):
    _disable_llm_cache(monkeypatch)
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "qwen3:1.7b")
    client = _mock_transport_client(
        monkeypatch,
        {
            "response": json.dumps({
                "skill_matches": ["Python"],
                "inferred_skills": [],
                "missing_critical": [],
                "semantic_reason": "Good match",
            }),
        },
    )

    result = OllamaLLMService.call_qwen("Score CV fit", "1.0", "thinking-model-cache-key")

    assert isinstance(result, QwenCVAnalysis)
    payload = _generation_payload(client)
    assert payload["prompt"] == "Score CV fit"
    assert payload["think"] is True


def test_legacy_thinking_directive_is_removed_before_generation(monkeypatch):
    _disable_llm_cache(monkeypatch)
    client = _mock_transport_client(
        monkeypatch,
        {
            "response": json.dumps({
                "skill_matches": ["Python"],
                "inferred_skills": [],
                "missing_critical": [],
                "semantic_reason": "Good match",
            }),
        },
    )

    result = OllamaLLMService.call_qwen("/think\nScore CV fit", "1.0", "legacy-directive-cache-key")

    assert isinstance(result, QwenCVAnalysis)
    payload = _generation_payload(client)
    assert payload["prompt"] == "Score CV fit"
    assert "think" not in payload


def test_ollama_unload_model_sends_keep_alive_zero(monkeypatch):
    client = _mock_transport_client(monkeypatch, {})

    success = OllamaLLMService.unload_model("llama3.2:3b")

    assert success is True
    payload = client.stream.call_args.kwargs["json"]
    assert payload["model"] == "llama3.2:3b"
    assert payload["keep_alive"] == 0


def test_domain_embedding_read_only_disables_live_generation(monkeypatch):
    from app.services.domain_embedding_service import DomainEmbeddingService

    called = False

    def mock_generate(*args, **kwargs):
        nonlocal called
        called = True
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(
        "app.services.embedding_service.EmbeddingService.generate_batch_embeddings",
        mock_generate,
    )

    result = DomainEmbeddingService.find_semantic_equivalents(
        term="uncached_skill_test_xyz",
        category="skills",
        allow_live_generation=False,
    )

    assert called is False
    assert isinstance(result, list)
