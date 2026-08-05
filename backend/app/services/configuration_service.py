import json
from typing import Optional
from sqlalchemy.orm import Session

from app.core.cache import RedisCache
from app.core.logging import logger
from app.models.rules import RuleConfigProfile
from app.core.rule_config_manager import UnifiedRuleConfig, RuleConfigManager

class ConfigurationService:
    REDIS_PUBSUB_CHANNEL = "cvai:config:invalidated"

    @classmethod
    def create_profile(
        cls,
        db: Session,
        version_tag: str,
        config: UnifiedRuleConfig,
        tenant_id: Optional[str] = None,
        description: Optional[str] = None,
        created_by: Optional[str] = None,
        audit_reason: Optional[str] = None,
    ) -> RuleConfigProfile:
        """Create a new version of the rule config."""
        
        # Validate that the config is valid before saving
        # This will raise an exception if it violates safety invariants
        RuleConfigManager._run_synthetic_smoke_tests(config)
        
        profile = RuleConfigProfile(
            version_tag=version_tag,
            tenant_id=tenant_id,
            description=description,
            global_confidence_tiers_json=json.dumps(config.global_confidence_tiers, default=lambda x: x.model_dump()),
            fields_config_json=json.dumps(config.fields, default=lambda x: x.model_dump()),
            scoring_rules_json=json.dumps(config.scoring.model_dump()),
            is_active=False,
            created_by=created_by,
            audit_reason=audit_reason,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    @classmethod
    def activate_profile(
        cls,
        db: Session,
        version_tag: str,
        tenant_id: Optional[str] = None,
        updated_by: Optional[str] = None,
        audit_reason: Optional[str] = None,
    ) -> RuleConfigProfile:
        """Activate a specific version and broadcast invalidation."""
        
        query = db.query(RuleConfigProfile).filter(RuleConfigProfile.version_tag == version_tag)
        if tenant_id:
            query = query.filter(RuleConfigProfile.tenant_id == tenant_id)
        else:
            query = query.filter(RuleConfigProfile.tenant_id.is_(None))
            
        profile_to_activate = query.first()
        
        if not profile_to_activate:
            raise ValueError(f"Profile {version_tag} not found for tenant {tenant_id}")

        # Deactivate all others for this tenant
        deactivate_query = db.query(RuleConfigProfile).filter(RuleConfigProfile.is_active == True)
        if tenant_id:
            deactivate_query = deactivate_query.filter(RuleConfigProfile.tenant_id == tenant_id)
        else:
            deactivate_query = deactivate_query.filter(RuleConfigProfile.tenant_id.is_(None))
            
        for p in deactivate_query.all():
            p.is_active = False

        profile_to_activate.is_active = True
        
        # Note: In a real system, you might record the updated_by / audit_reason here, 
        # but for now we just change the state.
        
        db.commit()
        db.refresh(profile_to_activate)

        cls._broadcast_invalidation(tenant_id)

        return profile_to_activate

    @classmethod
    def get_active_profile(cls, db: Session, tenant_id: Optional[str] = None) -> Optional[RuleConfigProfile]:
        query = db.query(RuleConfigProfile).filter(RuleConfigProfile.is_active == True)
        if tenant_id:
            query = query.filter(RuleConfigProfile.tenant_id == tenant_id)
        else:
            query = query.filter(RuleConfigProfile.tenant_id.is_(None))
        return query.first()

    @classmethod
    def _broadcast_invalidation(cls, tenant_id: Optional[str] = None):
        """Notify all workers to reload configuration."""
        client = RedisCache._get_client()
        if client:
            message = tenant_id if tenant_id else "GLOBAL"
            try:
                client.publish(cls.REDIS_PUBSUB_CHANNEL, message)
                logger.info(f"[CONFIG] Published invalidation event for {message}")
            except Exception as e:
                logger.error(f"[CONFIG] Failed to broadcast invalidation: {e}")
