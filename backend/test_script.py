import sys
from app.services.system_rule_config_factory import SystemRuleConfigFactory
from app.core.rule_config_manager import RuleConfigManager
from app.services.hiring_risk_analyzer import HiringRiskAnalyzer
from app.schemas.match import JobMatchResult

config = SystemRuleConfigFactory.build()
print(config.hiring_risks.policies)

match_result = JobMatchResult(
    job_id="test", job_title="test", department="test", score=50.0, classification="MEDIUM", recommendation="",
    mandatory_fails=[{"failure_code": "MIN_EXPERIENCE_FAILED", "requirement": "R", "details": "D", "impact": 10}]
)
RuleConfigManager.get_config = lambda: config

HiringRiskAnalyzer.generate_risks(match_result, None, None)
print(match_result.hiring_risks)
