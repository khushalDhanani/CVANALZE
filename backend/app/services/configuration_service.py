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
        """Create a new version of the rule config in DRAFT state."""
        
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
            status="DRAFT",
            created_by=created_by,
            audit_reason=audit_reason,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    @classmethod
    def request_approval(
        cls,
        db: Session,
        version_tag: str,
        tenant_id: Optional[str] = None,
    ) -> RuleConfigProfile:
        """Move a profile from DRAFT to PENDING_APPROVAL."""
        query = db.query(RuleConfigProfile).filter(RuleConfigProfile.version_tag == version_tag)
        if tenant_id:
            query = query.filter(RuleConfigProfile.tenant_id == tenant_id)
        else:
            query = query.filter(RuleConfigProfile.tenant_id.is_(None))
            
        profile = query.first()
        if not profile:
            raise ValueError(f"Profile {version_tag} not found for tenant {tenant_id}")
            
        if profile.status != "DRAFT":
            raise ValueError(f"Only DRAFT profiles can request approval, current status is {profile.status}")
            
        profile.status = "PENDING_APPROVAL"
        db.commit()
        db.refresh(profile)
        return profile

    @classmethod
    def activate_profile(
        cls,
        db: Session,
        version_tag: str,
        tenant_id: Optional[str] = None,
        activated_by: Optional[str] = None,
        activation_reason: Optional[str] = None,
    ) -> RuleConfigProfile:
        """Approve and activate a specific version, deactivating others, and broadcast invalidation."""
        from datetime import datetime, UTC
        
        query = db.query(RuleConfigProfile).filter(RuleConfigProfile.version_tag == version_tag)
        if tenant_id:
            query = query.filter(RuleConfigProfile.tenant_id == tenant_id)
        else:
            query = query.filter(RuleConfigProfile.tenant_id.is_(None))
            
        profile_to_activate = query.first()
        
        if not profile_to_activate:
            raise ValueError(f"Profile {version_tag} not found for tenant {tenant_id}")

        # Find currently active profile to capture previous_version_tag and rollback
        deactivate_query = db.query(RuleConfigProfile).filter(RuleConfigProfile.is_active == True)
        if tenant_id:
            deactivate_query = deactivate_query.filter(RuleConfigProfile.tenant_id == tenant_id)
        else:
            deactivate_query = deactivate_query.filter(RuleConfigProfile.tenant_id.is_(None))
            
        previous_active = deactivate_query.first()
        if previous_active:
            profile_to_activate.previous_version_tag = previous_active.version_tag
            previous_active.is_active = False
            previous_active.status = "ROLLED_BACK"

        # Strictly enforce exactly one active profile by disabling any others
        for p in deactivate_query.all():
            p.is_active = False
            if p.status == "ACTIVE":
                p.status = "ROLLED_BACK"

        profile_to_activate.is_active = True
        profile_to_activate.status = "ACTIVE"
        profile_to_activate.activated_by = activated_by
        profile_to_activate.activation_reason = activation_reason
        profile_to_activate.audit_reason = f"Activated by {activated_by}: {activation_reason}" if activated_by else (activation_reason or "System activation")
        profile_to_activate.activated_at = datetime.now(UTC)
        
        db.commit()
        db.refresh(profile_to_activate)

        cls._broadcast_invalidation(tenant_id)

        return profile_to_activate

    @classmethod
    def rollback_profile(
        cls,
        db: Session,
        tenant_id: Optional[str] = None,
        rolled_back_by: Optional[str] = None,
        rollback_reason: Optional[str] = None,
    ) -> RuleConfigProfile:
        """Rollback the currently active profile to its previous version."""
        from datetime import datetime, UTC
        
        query = db.query(RuleConfigProfile).filter(RuleConfigProfile.is_active == True)
        if tenant_id:
            query = query.filter(RuleConfigProfile.tenant_id == tenant_id)
        else:
            query = query.filter(RuleConfigProfile.tenant_id.is_(None))
            
        current_active = query.first()
        if not current_active:
            raise ValueError(f"No active profile found for tenant {tenant_id} to rollback")
            
        if not current_active.previous_version_tag:
            raise ValueError(f"Active profile {current_active.version_tag} has no previous_version_tag to rollback to")
            
        # Find the previous profile
        prev_query = db.query(RuleConfigProfile).filter(RuleConfigProfile.version_tag == current_active.previous_version_tag)
        if tenant_id:
            prev_query = prev_query.filter(RuleConfigProfile.tenant_id == tenant_id)
        else:
            prev_query = prev_query.filter(RuleConfigProfile.tenant_id.is_(None))
            
        profile_to_restore = prev_query.first()
        if not profile_to_restore:
            raise ValueError(f"Previous profile {current_active.previous_version_tag} not found")
            
        # Rollback current
        current_active.is_active = False
        current_active.status = "ROLLED_BACK"
        
        # Restore previous
        profile_to_restore.is_active = True
        profile_to_restore.status = "ACTIVE"
        profile_to_restore.activated_by = rolled_back_by
        profile_to_restore.activation_reason = rollback_reason or f"Rolled back from {current_active.version_tag}"
        profile_to_restore.audit_reason = f"Rolled back by {rolled_back_by}: {profile_to_restore.activation_reason}" if rolled_back_by else profile_to_restore.activation_reason
        profile_to_restore.activated_at = datetime.now(UTC)
        
        # We don't overwrite profile_to_restore.previous_version_tag to maintain history chain
        
        db.commit()
        db.refresh(profile_to_restore)
        
        cls._broadcast_invalidation(tenant_id)
        
        return profile_to_restore

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
