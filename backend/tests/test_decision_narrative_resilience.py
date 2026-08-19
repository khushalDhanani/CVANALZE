import pytest
from app.schemas.analysis import OptimizedVacancyMatch


def _base_vacancy_match(**kwargs) -> dict:
    return {
        "vacancy_id": 101,
        "semantic_reason": "Candidate has direct relevant experience for this role.",
        "top_strength": (
            "The candidate holds a B.Sc. in Computer Science with extensive hands-on experience in Python and FastAPI. "
            "They have delivered multiple production microservices."
        ),
        "main_concern": (
            "The candidate has limited Kubernetes experience e.g. in multi-cluster deployments. "
            "Recruiters should verify infrastructure ownership during technical interviews."
        ),
        "ai_match_explanation": (
            "The candidate matches 85% of core requirements based on strong Python and SQL background. "
            "Their 5+ years of relevant experience makes them a strong fit for the backend position."
        ),
        "semantic_fit_score": 85.0,
        "requirement_assessments": [],
        **kwargs,
    }


def test_decision_narrative_accepts_abbreviations():
    data = _base_vacancy_match(
        top_strength=(
            "The candidate holds a Ph.D. in Machine Learning and a B.Tech. in Computer Science. "
            "They have 6+ years of expertise in NLP pipelines e.g. BERT and GPT architectures."
        ),
        main_concern=(
            "The CV lacks evidence of cloud architecture vs. on-premise infrastructure. "
            "Recruiters should check AWS or GCP experience."
        ),
    )
    match = OptimizedVacancyMatch.model_validate(data)
    assert "Ph.D." in match.top_strength
    assert "B.Tech." in match.top_strength
    assert "e.g." in match.top_strength


def test_decision_narrative_auto_repairs_missing_period():
    data = _base_vacancy_match(
        top_strength=(
            "The candidate has 5+ years of software development experience across Python and Docker. "
            "Their backend API skills directly align with the core requirements"
        )
    )
    match = OptimizedVacancyMatch.model_validate(data)
    assert match.top_strength.endswith(".")


def test_decision_narrative_accepts_single_substantial_sentence():
    data = _base_vacancy_match(
        top_strength=(
            "The candidate demonstrates over eight years of distinguished engineering leadership across distributed Python architectures and cloud-native services."
        )
    )
    match = OptimizedVacancyMatch.model_validate(data)
    assert match.top_strength.startswith("The candidate demonstrates")


def test_decision_narrative_rejects_empty():
    data = _base_vacancy_match(top_strength="")
    with pytest.raises(Exception):
        OptimizedVacancyMatch.model_validate(data)


def test_tags_operation_does_not_require_file_lock(monkeypatch):
    import time
    from unittest.mock import MagicMock
    from app.services.ollama_transport import OllamaTransport

    # Mock client to return tags
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.iter_bytes.return_value = [b'{"models": [{"name": "llama3.2:3b"}]}']
    mock_client.stream.return_value.__enter__.return_value = mock_resp
    monkeypatch.setattr(OllamaTransport, "get_client", classmethod(lambda cls: mock_client))

    # Calling get_tags should succeed directly
    result = OllamaTransport.get_tags()
    assert result.value.models[0].name == "llama3.2:3b"


def test_admission_control_prunes_oversized_vacancies(monkeypatch):
    from unittest.mock import patch
    from app.core.config import settings
    from app.prompts.optimized_match import build_optimized_match_prompt

    # Mock a small token budget to trigger admission control
    monkeypatch.setattr(settings, "OLLAMA_OPTIMIZED_NUM_CTX", 2000)
    monkeypatch.setattr(settings, "OLLAMA_OPTIMIZED_NUM_PREDICT", 500)

    cv_text = "Senior Python Developer with 10 years experience."
    oversized_vacancies = [
        {
            "vacancy_id": i,
            "title": f"Senior Lead Architect {i}",
            "department": "Engineering",
            "required_skills": ["Python", "FastAPI", "Docker", "Kubernetes", "AWS", "PostgreSQL"],
            "responsibilities": ["Design microservices", "Manage engineering teams", "Lead infrastructure"],
            "description": "Long job description " * 50,
        }
        for i in range(1, 10)
    ]

    with patch("app.services.prompt_service.PromptService.get_prompt") as mock_prompt:
        mock_prompt.return_value = "Admission test prompt"
        prompt, tokens, chars = build_optimized_match_prompt(cv_text, oversized_vacancies)

    # Prompt tokens must stay strictly bounded within the admission budget (1500 tokens)
    assert tokens <= 1500

