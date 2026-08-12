from app.core.rule_config_manager import RuleConfigManager
try:
    RuleConfigManager.load_config()
    print("Loaded OK")
except Exception as e:
    print("Error:", e)
