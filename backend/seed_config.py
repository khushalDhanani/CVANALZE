from app.core.database import PostgresAppSession
from app.services.system_rule_config_factory import SystemRuleConfigFactory
from app.services.configuration_service import ConfigurationService
db = PostgresAppSession()
config = SystemRuleConfigFactory.build()
profile = ConfigurationService.create_profile(db, version_tag="system-default-v3", config=config, description="Seeded with keywords")
ConfigurationService.activate_profile(db, "system-default-v3")
db.commit()
print("Bootstrapped config v3")
