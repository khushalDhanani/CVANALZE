from app.core.rule_config_manager import RuleConfigManager
print("Starters:", RuleConfigManager.get_keywords("job_title", "narrative_starters"))
print("Phrases:", RuleConfigManager.get_keywords("job_title", "narrative_phrases"))
