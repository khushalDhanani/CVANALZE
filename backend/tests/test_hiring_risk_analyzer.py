from unittest.mock import patch
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.core.rule_config_manager import HiringRiskPolicy
from app.repositories.result import ResultRepository
from app.schemas.match import JobMatchResult, MandatoryFailureDetails, RiskSeverity
from app.services.hiring_risk_analyzer import HiringRiskAnalyzer, HiringRiskExplanationsOutput
from app.services.prompt_service import ResolvedPrompt
from app.services.system_rule_config_factory import SystemRuleConfigFactory


def build_result(*, failure_code: str | None = None, requirement_id: str = "req_test", missing_skills: list[str] | None = None) -> JobMatchResult:
    failures = []
    if failure_code:
        failures.append(
            MandatoryFailureDetails(
                failure_code=failure_code,
                requirement_id=requirement_id,
                description="Structured requirement",
                reason="Structured deterministic evidence",
                score_impact=10.0,
            )
        )
    return JobMatchResult(
        job_id="test_job",
        job_title="Test Job",
        department="Test Dept",
        score=50.0,
        overall_score=50.0,
        vacancy_fit_score=50.0,
        classification="MEDIUM",
        recommendation="",
        mandatory_failures=failures,
        missing_skills=missing_skills or [],
    )


@pytest.fixture(autouse=True)
def risk_dependencies():
    config = SystemRuleConfigFactory.build()
    with patch("app.services.hiring_risk_analyzer.RuleConfigManager.get_config", return_value=config), patch(
        "app.services.hiring_risk_analyzer.PromptService.get_prompt_with_version",
        side_effect=lambda _name, placeholders, **_kwargs: ResolvedPrompt(placeholders["prompt_payload"], "risk-prompt-v1"),
    ):
        yield config


def test_mandatory_experience_failure_uses_structured_code():
    match_result = build_result(failure_code="MIN_EXPERIENCE_FAILED", requirement_id="req_exp")

    HiringRiskAnalyzer.generate_risks(match_result, None, None)

    assert len(match_result.hiring_risks) == 1
    risk = match_result.hiring_risks[0]
    assert risk.risk_code == "MIN_EXPERIENCE_FAILED"
    assert risk.category == "Experience"
    assert risk.severity == RiskSeverity.CRITICAL


def test_new_configured_failure_code_requires_no_analyzer_branch(risk_dependencies):
    risk_dependencies.hiring_risks.policies["NEW_CONFIGURED_CODE"] = HiringRiskPolicy(
        enabled=True,
        severity="HIGH",
        manual_review=True,
        category="Compliance",
        source="ConfiguredEvaluator",
    )
    match_result = build_result(failure_code="NEW_CONFIGURED_CODE")

    HiringRiskAnalyzer.generate_risks(match_result, None, None)

    assert len(match_result.hiring_risks) == 1
    assert match_result.hiring_risks[0].category == "Compliance"
    assert match_result.hiring_risks[0].source == "ConfiguredEvaluator"


def test_unknown_and_disabled_policies_are_distinct(risk_dependencies, caplog):
    caplog.set_level("DEBUG")
    risk_dependencies.hiring_risks.policies["DISABLED_CODE"] = HiringRiskPolicy(
        enabled=False,
        severity="LOW",
        manual_review=False,
    )
    disabled_result = build_result(failure_code="DISABLED_CODE")
    unknown_result = build_result(failure_code="UNKNOWN_CODE")

    HiringRiskAnalyzer.generate_risks(disabled_result, None, None)
    HiringRiskAnalyzer.generate_risks(unknown_result, None, None)

    assert disabled_result.hiring_risks == []
    assert unknown_result.hiring_risks == []
    assert "disabled risk code" in caplog.text
    assert "unknown risk code" in caplog.text


def test_education_risk_is_deferred_even_when_enabled(risk_dependencies):
    risk_dependencies.hiring_risks.policies["EDUCATION_MISMATCH"] = HiringRiskPolicy(
        enabled=True,
        severity="HIGH",
        manual_review=True,
        category="Education",
    )
    match_result = build_result(failure_code="EDUCATION_MISMATCH", requirement_id="req_education")

    HiringRiskAnalyzer.generate_risks(match_result, None, None)

    assert match_result.hiring_risks == []


@patch("app.services.hiring_risk_analyzer.OllamaLLMService.generate_structured_json")
def test_gemma_unavailable_keeps_deterministic_risk(mock_generate):
    mock_generate.side_effect = RuntimeError("Ollama down")
    match_result = build_result(missing_skills=["Python"])

    HiringRiskAnalyzer.generate_risks(match_result, None, None)

    assert match_result.hiring_risks[0].title == "Detected MISSING_MANDATORY_SKILL"


def test_prompt_unavailable_keeps_deterministic_risk():
    match_result = build_result(missing_skills=["Python"])
    with patch(
        "app.services.hiring_risk_analyzer.PromptService.get_prompt_with_version",
        side_effect=RuntimeError("Prompt unavailable"),
    ):
        HiringRiskAnalyzer.generate_risks(match_result, None, None)

    assert match_result.hiring_risks[0].risk_code == "MISSING_MANDATORY_SKILL"


@pytest.mark.parametrize("failure_mode", ["malformed_json", "schema_validation_failure"])
@patch("app.services.hiring_risk_analyzer.OllamaLLMService.generate_structured_json", return_value=None)
def test_invalid_structured_output_keeps_deterministic_risk(mock_generate, failure_mode):
    match_result = build_result(missing_skills=["Python"])

    HiringRiskAnalyzer.generate_risks(match_result, None, None)

    assert failure_mode in {"malformed_json", "schema_validation_failure"}
    assert match_result.hiring_risks[0].explanation == "Missing mandatory skills: Python"


@patch("app.services.hiring_risk_analyzer.OllamaLLMService.generate_structured_json")
def test_gemma_can_only_update_existing_title_and_explanation(mock_generate):
    mock_generate.return_value = HiringRiskExplanationsOutput.model_validate(
        {
            "explanations": [
                {"risk_code": "MISSING_MANDATORY_SKILL", "title": "Verified gap", "explanation": "Python evidence is absent."},
                {"risk_code": "INVENTED_RISK", "title": "Invented", "explanation": "Must be ignored."},
            ]
        }
    )
    match_result = build_result(missing_skills=["Python"])

    HiringRiskAnalyzer.generate_risks(match_result, None, None)

    assert len(match_result.hiring_risks) == 1
    risk = match_result.hiring_risks[0]
    assert risk.risk_code == "MISSING_MANDATORY_SKILL"
    assert risk.title == "Verified gap"
    assert risk.category == "Skills"
    assert risk.requires_manual_review is False


@pytest.mark.parametrize("field", ["severity", "category", "requires_manual_review", "source"])
def test_explanation_schema_rejects_tampered_fields(field):
    payload = {
        "explanations": [
            {"risk_code": "MIN_EXPERIENCE_FAILED", "title": "Title", "explanation": "Explanation", field: "tampered"}
        ]
    }

    with pytest.raises(ValidationError):
        HiringRiskExplanationsOutput.model_validate(payload)


@patch("app.services.hiring_risk_analyzer.OllamaLLMService.generate_structured_json", return_value=None)
def test_explanation_cache_key_changes_with_prompt_model_and_policy(mock_generate, monkeypatch):
    match_result = build_result(missing_skills=["Python"])
    risks = []
    HiringRiskAnalyzer.generate_risks(match_result, None, None)
    risks.extend(match_result.hiring_risks)
    first_key = mock_generate.call_args.kwargs["cache_key"]

    mock_generate.reset_mock()
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "different-model")
    with patch(
        "app.services.hiring_risk_analyzer.PromptService.get_prompt_with_version",
        return_value=ResolvedPrompt("CHANGED PROMPT", "risk-prompt-v2"),
    ):
        HiringRiskAnalyzer._generate_explanations(risks, match_result, "policy-v2")
    second_key = mock_generate.call_args.kwargs["cache_key"]

    assert first_key != second_key


@patch("app.services.hiring_risk_analyzer.OllamaLLMService.generate_structured_json", return_value=None)
def test_payload_excludes_candidate_identity_and_raw_cv(mock_generate):
    match_result = build_result(missing_skills=["Python"])
    match_result.job_title = "Software Engineer"
    context = SimpleNamespace(
        resume_json={
            "contact_info": {
                "name": "Jane Candidate",
                "email": "jane@example.com",
                "phone": "+91 9876543210",
                "gender": "Female",
                "nationality": "Indian",
                "address": "Private Street",
            }
        }
    )
    match_result.missing_skills = ["Python; Email: jane@example.com; Phone: +91 9876543210; Gender: Female"]

    HiringRiskAnalyzer.generate_risks(match_result, context, None)

    prompt = mock_generate.call_args.kwargs["prompt"]
    for protected_value in ("candidate_name", "email", "phone", "dob", "age", "gender", "nationality", "address", "raw_cv_text"):
        assert protected_value not in prompt.lower()
    assert "jane@example.com" not in prompt
    assert "9876543210" not in prompt
    assert "Female" not in prompt


def test_high_risk_output_preserves_score_and_status():
    match_result = build_result(missing_skills=["Python"])
    original_score = match_result.vacancy_fit_score
    original_status = match_result.vacancy_match_status

    HiringRiskAnalyzer.generate_risks(match_result, None, None)

    assert match_result.vacancy_fit_score == original_score
    assert match_result.vacancy_match_status == original_status


def test_model_dump_preserves_complete_hiring_risk_contract():
    match_result = build_result(missing_skills=["Python"])

    HiringRiskAnalyzer.generate_risks(match_result, None, None)

    serialized = match_result.model_dump()["hiring_risks"][0]
    assert set(serialized) == {
        "risk_code",
        "category",
        "severity",
        "title",
        "explanation",
        "evidence",
        "source",
        "requires_manual_review",
    }


def test_stale_persisted_risks_are_suppressed_without_recalculation():
    stale_result = {
        "rule_config_version": "old-rule",
        "hiring_risk_policy_version": "old-policy",
        "hiring_risk_prompt_version": "old-prompt",
        "llm_model_version": "old-model",
        "match_analysis": {
            "best_match": {"hiring_risks": [{"risk_code": "STALE", "explanation": "stale"}]},
            "suitable_openings": [{"hiring_risks": [{"risk_code": "STALE", "explanation": "stale"}]}],
        },
    }

    sanitized = ResultRepository.enforce_hiring_risk_freshness(stale_result)

    assert sanitized["hiring_risks_stale"] is True
    assert sanitized["match_analysis"]["best_match"]["hiring_risks"] == []
    assert sanitized["match_analysis"]["suitable_openings"][0]["hiring_risks"] == []
    assert stale_result["match_analysis"]["best_match"]["hiring_risks"]
