from app.core.database import init_db
from app.core.rule_config_manager import RuleConfigManager
init_db()
config = RuleConfigManager.load_config()
print("LOAD SUCCESS, fields:", len(config.fields))
