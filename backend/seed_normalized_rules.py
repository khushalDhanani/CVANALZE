"""Seed the normalized rule configuration profile from MOCK_RULE_CONFIG for local development."""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.database import PostgresAppSession, init_db
from app.services.configuration_service import ConfigurationService
from app.core.rule_config_manager import UnifiedRuleConfig
from app.models.rules import RuleConfigProfile
from tests.mock_rule_config import MOCK_RULE_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_normalized_rules")


def seed():
    init_db()
    db = PostgresAppSession()
    try:
        config_model = UnifiedRuleConfig.model_validate(MOCK_RULE_CONFIG)
        version_tag = config_model.version

        # Remove any existing profile with same version
        existing = db.query(RuleConfigProfile).filter_by(version_tag=version_tag).first()
        if existing:
            logger.info(f"Deleting existing profile v{version_tag}...")
            db.delete(existing)
            db.commit()

        logger.info(f"Creating normalized profile v{version_tag}...")
        profile = ConfigurationService.create_profile(
            db=db,
            version_tag=version_tag,
            config=config_model,
            description="Normalized Default Config seeded from MOCK_RULE_CONFIG",
            created_by="system",
        )

        # Manually activate (bypass Redis pubsub which may not be available)
        profile.status = "ACTIVE"
        profile.is_active = True
        db.commit()

        # Verify round-trip
        logger.info("Verifying round-trip hydration...")
        from app.core.rule_config_manager import RuleConfigManager
        loaded = RuleConfigManager.load_config(tenant_id=None)
        logger.info(f"Round-trip SUCCESS: v{loaded.version}, {len(loaded.fields)} fields, {len(loaded.scoring.taxonomy.vacancy_rules)} vacancy rules")
        logger.info(f"  domain_embedding categories: {loaded.scoring.domain_embedding.categories}")
        logger.info(f"  term_matching aliases: {list(loaded.scoring.match.term_matching.aliases.keys())}")
        logger.info("Seed complete.")

    except Exception as e:
        logger.error(f"Seed failed: {e}", exc_info=True)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
