import pytest
import json
from unittest.mock import patch, MagicMock

from app.schemas.match import JobMatchResult, RiskSeverity, HiringRisk
from app.services.hiring_risk_analyzer import HiringRiskAnalyzer
from app.core.rule_config_manager import RuleConfigManager, UnifiedRuleConfig
from app.services.system_rule_config_factory import SystemRuleConfigFactory

def mock_get_config():
    config = SystemRuleConfigFactory.build()
    return config

@pytest.fixture(autouse=True)
def mock_rule_config():
    with patch("app.core.rule_config_manager.RuleConfigManager.get_config", side_effect=mock_get_config):
        yield

class TestHiringRiskAnalyzer:
    def create_mock_result(self, mandatory_fails=None, missing_skills=None, domain_capped=False):
        return JobMatchResult(
            job_id="test_job",
            job_title="Test Job",
            department="Test Dept",
            score=50.0,
            overall_score=50.0,
            vacancy_fit_score=50.0,
            classification="MEDIUM",
            recommendation="",
            mandatory_fails=mandatory_fails or [],
            missing_skills=missing_skills or [],
            domain_mismatch_capped=domain_capped,
            domain_mismatch_reason="Mismatch" if domain_capped else None
        )

    def test_mandatory_experience_failure(self):
        match_result = self.create_mock_result(
            mandatory_fails=[
                {"failure_code": "MIN_EXPERIENCE_FAILED", "requirement": "Minimum Experience: 3.0", "details": "Only 0.0", "impact": 10}
            ]
        )
        HiringRiskAnalyzer.generate_risks(match_result, None, None)
        assert len(match_result.hiring_risks) == 1
        risk = match_result.hiring_risks[0]
        assert risk.risk_code == "MIN_EXPERIENCE_FAILED"
        assert risk.severity == RiskSeverity.CRITICAL
        assert risk.requires_manual_review is False

    def test_unknown_experience_risk(self):
        match_result = self.create_mock_result(
            mandatory_fails=[
                {"failure_code": "EXPERIENCE_UNKNOWN", "requirement": "Minimum Experience: 3.0", "details": "UNKNOWN due to unparseable dates", "impact": 10}
            ]
        )
        HiringRiskAnalyzer.generate_risks(match_result, None, None)
        assert len(match_result.hiring_risks) == 1
        risk = match_result.hiring_risks[0]
        assert risk.risk_code == "EXPERIENCE_UNKNOWN"
        assert risk.severity == RiskSeverity.UNKNOWN
        assert risk.requires_manual_review is True

    def test_no_deterministic_risk_evidence(self):
        match_result = self.create_mock_result()
        HiringRiskAnalyzer.generate_risks(match_result, None, None)
        assert len(match_result.hiring_risks) == 0

    @patch("app.services.llm_service.OllamaLLMService.generate_structured_json")
    def test_gemma_unavailable_fallback(self, mock_generate):
        mock_generate.side_effect = Exception("Ollama Down")
        match_result = self.create_mock_result(missing_skills=["Python"])
        HiringRiskAnalyzer.generate_risks(match_result, None, None)
        
        # Should still generate the deterministic risk, just without LLM explanation
        assert len(match_result.hiring_risks) == 1
        risk = match_result.hiring_risks[0]
        assert risk.risk_code == "MISSING_MANDATORY_SKILL"
        assert risk.title == "Detected MISSING_MANDATORY_SKILL" # Deterministic fallback

    @patch("app.services.llm_service.OllamaLLMService.generate_structured_json")
    def test_gemma_hallucinates_extra_risk(self, mock_generate):
        from pydantic import BaseModel
        class Explanation(BaseModel):
            risk_code: str
            title: str
            explanation: str
        class ExplanationsOutput(BaseModel):
            explanations: list[Explanation]
            
        mock_obj = MagicMock()
        mock_obj.validated = ExplanationsOutput(explanations=[
            Explanation(risk_code="MISSING_MANDATORY_SKILL", title="LLM Title", explanation="LLM Explanation."),
            Explanation(risk_code="INVENTED_RISK", title="Bad Attitude", explanation="Grumpy.")
        ])
        mock_generate.return_value = mock_obj
        
        match_result = self.create_mock_result(missing_skills=["Python"])
        HiringRiskAnalyzer.generate_risks(match_result, None, None)
        
        assert len(match_result.hiring_risks) == 1 # Invented risk ignored
        risk = match_result.hiring_risks[0]
        assert risk.risk_code == "MISSING_MANDATORY_SKILL"
        assert risk.title == "LLM Title"
        assert risk.explanation == "LLM Explanation."

    def test_high_risk_output_preserves_score(self):
        match_result = self.create_mock_result(missing_skills=["Python"])
        original_score = match_result.vacancy_fit_score
        original_status = match_result.vacancy_match_status
        
        HiringRiskAnalyzer.generate_risks(match_result, None, None)
        
        assert match_result.vacancy_fit_score == original_score
        assert match_result.vacancy_match_status == original_status

    def test_unknown_risk_code_ignored(self):
        match_result = self.create_mock_result(
            mandatory_fails=[
                {"failure_code": "SOME_WEIRD_CODE", "requirement": "Test", "details": "...", "impact": 10}
            ]
        )
        HiringRiskAnalyzer.generate_risks(match_result, None, None)
        assert len(match_result.hiring_risks) == 0

    @patch("app.core.rule_config_manager.RuleConfigManager.get_config")
    def test_disabled_policy_no_risk(self, mock_get_config):
        config = SystemRuleConfigFactory.build()
        # Remove it from dict
        config.hiring_risks.policies.pop("MIN_EXPERIENCE_FAILED", None)
        mock_get_config.return_value = config
        
        match_result = self.create_mock_result(
            mandatory_fails=[
                {"failure_code": "MIN_EXPERIENCE_FAILED", "requirement": "Test", "details": "...", "impact": 10}
            ]
        )
        HiringRiskAnalyzer.generate_risks(match_result, None, None)
        assert len(match_result.hiring_risks) == 0

    def test_education_risk_deferred(self):
        match_result = self.create_mock_result(
            mandatory_fails=[
                {"failure_code": "EDUCATION_MISMATCH", "requirement": "Test", "details": "...", "impact": 10}
            ]
        )
        HiringRiskAnalyzer.generate_risks(match_result, None, None)
        # Not configured in policies = safely ignored!
        assert len(match_result.hiring_risks) == 0
