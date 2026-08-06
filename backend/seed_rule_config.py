import json
from app.core.database import PostgresAppSession, init_db
from app.models.rules import RuleConfigProfile
from pathlib import Path

def seed():
    init_db()
    db = PostgresAppSession()
    try:
        rule_config_path = Path("app/core/rule_config.json")
        with open(rule_config_path) as f:
            rule_data = json.load(f)
            
        version = rule_data.get("version", "1.1.0")
        profile = db.query(RuleConfigProfile).filter_by(version_tag=version).first()
        if not profile:
            profile = RuleConfigProfile(version_tag=version)
            db.add(profile)
            
        profile.description = rule_data.get("description", "Auto-seeded")
        profile.global_confidence_tiers_json = json.dumps(rule_data.get("global_confidence_tiers", {}))
        profile.fields_config_json = json.dumps(rule_data.get("fields", {}))
        profile.scoring_rules_json = json.dumps(rule_data.get("scoring", {}))
        profile.status = "PUBLISHED"
        profile.is_active = True
        profile.created_by = "system"
        db.commit()
        print("Successfully seeded active RuleConfigProfile.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
