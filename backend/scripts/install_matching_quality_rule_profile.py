"""Install and activate the complete system matching-rule profile."""
from __future__ import annotations

import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import PostgresAppSession
from app.services.configuration_service import ConfigurationService
from app.services.system_rule_config_factory import SystemRuleConfigFactory


def install() -> str:
    config = SystemRuleConfigFactory.build()
    with PostgresAppSession() as db:
        existing = ConfigurationService.get_profile(db, config.version, tenant_id=None)
        if existing is None:
            ConfigurationService.create_profile(
                db=db,
                version_tag=config.version,
                config=config,
                description=config.description,
                created_by="matching-quality-repair",
                audit_reason="Install complete governed term-matching assets",
            )
        active = ConfigurationService.activate_profile(
            db=db,
            version_tag=config.version,
            tenant_id=None,
            activated_by="matching-quality-repair",
            activation_reason="Required matching configuration readiness repair",
        )
        return active.version_tag


if __name__ == "__main__":
    print(install())
