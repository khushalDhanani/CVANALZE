import json
from unittest.mock import MagicMock, patch

import httpx

from app.core.config import settings
from app.schemas.analysis import (
    DynamicMappingResponse,
    OptimizedLLMMatchResponse,
    QwenCVAnalysis,
)
from app.schemas.profile import DynamicCandidateProfile
from app.services.llm_service import OllamaLLMService


def test_ollama_default_model_is_qwen3_4b():
    assert settings.OLLAMA_MODEL == "qwen3:4b"


def test_extract_candidate_profile_payload_and_prompt(monkeypatch):
    monkeypatch.setattr("app.repositories.llm_cache.LLMCacheRepository.get_cached_entry", lambda key: None)
    monkeypatch.setattr("app.repositories.llm_cache.LLMCacheRepository.save_cached_entry", lambda key, entry: None)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.raise_for_status.return_value = None
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
    mock_response.json.return_value = {
        "response": json.dumps(dummy_profile),
        "eval_count": 100,
        "eval_duration": 1000000000,
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    with patch("httpx.Client", return_value=mock_client):
        result = OllamaLLMService.extract_candidate_profile(
            prompt="Extract candidate CV details",
            prompt_version="1.0",
            cache_key="test_extraction_cache_key",
        )

    assert result is not None
    assert isinstance(result, DynamicCandidateProfile)
    assert mock_client.post.called

    call_args = mock_client.post.call_args
    payload = call_args[1]["json"]

    assert payload["model"] == "qwen3:4b"
    assert payload["prompt"].startswith("/no_think")
    assert payload["think"] is False
    assert payload["format"] == DynamicCandidateProfile.model_json_schema()
    assert payload["options"]["temperature"] == 0.0


def test_call_qwen_scoring_payload_and_prompt(monkeypatch):
    monkeypatch.setattr("app.repositories.llm_cache.LLMCacheRepository.get_cached_entry", lambda key: None)
    monkeypatch.setattr("app.repositories.llm_cache.LLMCacheRepository.save_cached_entry", lambda key, entry: None)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.raise_for_status.return_value = None
    dummy_analysis = {
        "skill_matches": ["Python"],
        "inferred_skills": ["FastAPI"],
        "missing_critical": [],
        "semantic_reason": "Good match",
    }
    mock_response.json.return_value = {
        "response": json.dumps(dummy_analysis),
        "eval_count": 100,
        "eval_duration": 1000000000,
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    with patch("httpx.Client", return_value=mock_client):
        result = OllamaLLMService.call_qwen(
            prompt="Score CV fit for Python Developer",
            prompt_version="1.0",
            cache_key="test_call_qwen_cache_key",
        )

    assert result is not None
    assert isinstance(result, QwenCVAnalysis)

    payload = mock_client.post.call_args[1]["json"]
    assert payload["model"] == "qwen3:4b"
    assert payload["prompt"].startswith("/think")
    assert payload["think"] is True
    assert payload["format"] == QwenCVAnalysis.model_json_schema()
    assert payload["options"]["temperature"] == 0.0


def test_call_qwen_dynamic_scoring_payload_and_prompt(monkeypatch):
    monkeypatch.setattr("app.repositories.llm_cache.LLMCacheRepository.get_cached_entry", lambda key: None)
    monkeypatch.setattr("app.repositories.llm_cache.LLMCacheRepository.save_cached_entry", lambda key, entry: None)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.raise_for_status.return_value = None
    dummy_mapping = {
        "matched_vacancies": [
            {
                "vacancy_id": 101,
                "semantic_reason": "Matched backend skill set",
                "inferred_skills": ["Docker"],
            }
        ]
    }
    mock_response.json.return_value = {
        "response": json.dumps(dummy_mapping),
        "eval_count": 100,
        "eval_duration": 1000000000,
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    with patch("httpx.Client", return_value=mock_client):
        result = OllamaLLMService.call_qwen_dynamic(
            prompt="Score candidate dynamic mapping",
            prompt_version="2.0",
            cache_key="test_dynamic_cache_key",
        )

    assert result is not None
    assert isinstance(result, DynamicMappingResponse)

    payload = mock_client.post.call_args[1]["json"]
    assert payload["model"] == "qwen3:4b"
    assert payload["prompt"].startswith("/think")
    assert payload["think"] is True
    assert payload["format"] == DynamicMappingResponse.model_json_schema()
    assert payload["options"]["temperature"] == 0.0


def test_run_optimized_match_scoring_payload_and_prompt(monkeypatch):
    monkeypatch.setattr("app.repositories.llm_cache.LLMCacheRepository.get_cached_entry", lambda key: None)
    monkeypatch.setattr("app.repositories.llm_cache.LLMCacheRepository.save_cached_entry", lambda key, entry: None)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.raise_for_status.return_value = None
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
                "semantic_fit_score": 90.0,
            }
        ],
    }
    mock_response.json.return_value = {
        "response": json.dumps(dummy_optimized),
        "eval_count": 120,
        "eval_duration": 1500000000,
    }

    mock_httpx_client = MagicMock()
    mock_httpx_client.post.return_value = mock_response

    with patch("app.services.llm_service._get_httpx_client", return_value=mock_httpx_client):
        result = OllamaLLMService.run_optimized_match(
            prompt="Perform optimized match evaluation",
            prompt_version="3.0",
            cache_key="test_optimized_match_cache_key",
        )

    assert result is not None
    assert isinstance(result, OptimizedLLMMatchResponse)

    payload = mock_httpx_client.post.call_args[1]["json"]
    assert payload["model"] == "qwen3:4b"
    assert payload["prompt"].startswith("/think")
    assert payload["think"] is True
    assert payload["format"] == OptimizedLLMMatchResponse.model_json_schema()
    assert payload["options"]["temperature"] == 0.0


def test_ollama_unload_model_sends_keep_alive_zero():
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.raise_for_status.return_value = None

    mock_httpx_client = MagicMock()
    mock_httpx_client.post.return_value = mock_response

    with patch("app.services.llm_service._get_httpx_client", return_value=mock_httpx_client):
        success = OllamaLLMService.unload_model("qwen3:4b")

    assert success is True
    assert mock_httpx_client.post.called
    call_args = mock_httpx_client.post.call_args
    payload = call_args[1]["json"]
    assert payload["model"] == "qwen3:4b"
    assert payload["keep_alive"] == 0


def test_domain_embedding_read_only_disables_live_generation(monkeypatch):
    from app.services.domain_embedding_service import DomainEmbeddingService

    called = False

    def mock_generate(*args, **kwargs):
        nonlocal called
        called = True
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr("app.services.embedding_service.EmbeddingService.generate_embedding", mock_generate)

    # When allow_live_generation=False and DB returns None, generate_embedding should NOT be called
    res = DomainEmbeddingService.find_semantic_equivalents(
        term="uncached_skill_test_xyz", category="skills", allow_live_generation=False
    )

    assert called is False
    assert isinstance(res, list)

