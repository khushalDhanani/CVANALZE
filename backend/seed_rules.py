import json
import logging
from app.core.database import PostgresAppSession, init_db
from app.models.rules import RuleConfigProfile
from app.models.domain import DepartmentDomainMaster
from tests.mock_rule_config import MOCK_RULE_CONFIG

logging.basicConfig(level=logging.INFO)

def seed():
    init_db()
    db = PostgresAppSession()
    try:
        version = MOCK_RULE_CONFIG.get("version", "1.1.0")
        profile = db.query(RuleConfigProfile).filter_by(version_tag=version).first()
        if not profile:
            profile = RuleConfigProfile(version_tag=version)
            db.add(profile)
            
        profile.description = MOCK_RULE_CONFIG.get("description", "Mocked Rule Config")
        profile.global_confidence_tiers_json = json.dumps(MOCK_RULE_CONFIG.get("global_confidence_tiers", {}))
        profile.fields_config_json = json.dumps(MOCK_RULE_CONFIG.get("fields", {}))
        profile.scoring_rules_json = json.dumps(MOCK_RULE_CONFIG.get("scoring", {}))
        profile.status = "PUBLISHED"
        profile.is_active = True
        profile.created_by = "system"
        db.commit()
        logging.info("Successfully seeded active RuleConfigProfile from MOCK_RULE_CONFIG.")
    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
