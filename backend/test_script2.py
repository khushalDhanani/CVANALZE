from app.services.system_rule_config_factory import SystemRuleConfigFactory
config = SystemRuleConfigFactory.build()
print(config.model_dump()["hiring_risks"])
