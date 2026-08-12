from app.core.rule_config_manager import HiringRiskConfig, HiringRiskPolicy
c = HiringRiskConfig(policies={"TEST": HiringRiskPolicy(severity="CRITICAL", manual_review=False)})
print(c.model_dump())
