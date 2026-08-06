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
        RuleConfigManager._run_synthetic_smoke_tests(config)
        
        from app.models.rules import RuleComponent, SystemRule, RuleCondition, RuleThreshold, RulePenalty, RuleWeight
        
        profile = RuleConfigProfile(
            version_tag=version_tag,
            tenant_id=tenant_id,
            description=description,
            is_active=False,
            status="DRAFT",
            created_by=created_by,
            audit_reason=audit_reason,
        )
        db.add(profile)
        db.flush()  # to get profile.profile_id if needed, though SQLAlchemy relationship appending handles it

        # 1. Global Tiers
        global_comp = RuleComponent(component_type="global_tiers", component_name="global", profile=profile)
        for tier_name, tier_bounds in config.global_confidence_tiers.items():
            global_comp.thresholds.append(RuleThreshold(threshold_key=f"{tier_name}_min", threshold_value=tier_bounds.min_score))
            global_comp.thresholds.append(RuleThreshold(threshold_key=f"{tier_name}_max", threshold_value=tier_bounds.max_score))
            
        # 2. Fields
        for field_name, field_cfg in config.fields.items():
            field_comp = RuleComponent(component_type="field", component_name=field_name, profile=profile)
            # Thresholds
            field_comp.thresholds.append(RuleThreshold(threshold_key="high_min", threshold_value=field_cfg.tier_thresholds.high_min))
            field_comp.thresholds.append(RuleThreshold(threshold_key="medium_min", threshold_value=field_cfg.tier_thresholds.medium_min))
            field_comp.thresholds.append(RuleThreshold(threshold_key="low_min", threshold_value=field_cfg.tier_thresholds.low_min))
            field_comp.thresholds.append(RuleThreshold(threshold_key="min_acceptance_confidence", threshold_value=field_cfg.downstream_gates.min_acceptance_confidence))
            
            # System rules for confidence scoring
            for k, v in field_cfg.confidence_scoring.items():
                field_comp.weights.append(RuleWeight(weight_key=f"confidence_{k}", weight_value=v))
                
            # Conditions (Keywords)
            rule = SystemRule(rule_type="keywords", rule_name="field_keywords", component=field_comp)
            for k, kw_list in field_cfg.keywords.items():
                rule.conditions.append(RuleCondition(condition_scope=k, keywords_json=json.dumps(kw_list)))

        # 3. Scoring - Match
        match_comp = RuleComponent(component_type="scoring", component_name="match", profile=profile)
        match_cfg = config.scoring.match
        
        # Scoring parameters
        for k, v in match_cfg.scoring_parameters.model_dump().items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                if "penalty" in k or "mismatch" in k:
                    match_comp.penalties.append(RulePenalty(penalty_key=k, penalty_value=float(v)))
                elif "weight" in k:
                    match_comp.weights.append(RuleWeight(weight_key=k, weight_value=float(v)))
                else:
                    match_comp.thresholds.append(RuleThreshold(threshold_key=k, threshold_value=float(v)))
            elif isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    if isinstance(sub_v, (int, float)):
                        match_comp.weights.append(RuleWeight(weight_key=f"{k}_{sub_k}", weight_value=float(sub_v)))
                        
        # 4. Scoring - Prefilter
        pref_comp = RuleComponent(component_type="scoring", component_name="prefilter", profile=profile)
        pref_cfg = config.scoring.prefilter
        for k, v in pref_cfg.lexical_weights.model_dump().items():
            if isinstance(v, (int, float)):
                pref_comp.weights.append(RuleWeight(weight_key=k, weight_value=float(v)))
        pref_comp.thresholds.append(RuleThreshold(threshold_key="rrf_k_constant", threshold_value=pref_cfg.rrf_k_constant))
        
        # 5. Scoring - Taxonomy
        tax_comp = RuleComponent(component_type="scoring", component_name="taxonomy", profile=profile)
        tax_cfg = config.scoring.taxonomy
        for vac_rule in tax_cfg.vacancy_rules:
            sys_rule = SystemRule(rule_type="vacancy_taxonomy", rule_name=vac_rule.name, target_value=f"{vac_rule.domain}::{vac_rule.family}", component=tax_comp)
            for branch in vac_rule.branches:
                for cond in branch.conditions:
                    sys_rule.conditions.append(RuleCondition(
                        condition_scope=cond.scope,
                        condition_mode=cond.mode,
                        is_negated=cond.negate,
                        keywords_json=json.dumps(cond.keywords)
                    ))

        for cand_rule in tax_cfg.candidate_rules:
            sys_rule = SystemRule(rule_type="candidate_taxonomy", rule_name=cand_rule.name, target_value=f"{cand_rule.domain}::{','.join(cand_rule.families)}", component=tax_comp)
            for branch in cand_rule.branches:
                for cond in branch.conditions:
                    sys_rule.conditions.append(RuleCondition(
                        condition_scope=cond.scope,
                        condition_mode=cond.mode,
                        is_negated=cond.negate,
                        keywords_json=json.dumps(cond.keywords)
                    ))
                    
        # 6. Scoring - Resume Quality
        rq_comp = RuleComponent(component_type="scoring", component_name="resume_quality", profile=profile)
        rq_cfg = config.scoring.resume_quality
        rq_comp.weights.append(RuleWeight(weight_key="section_weight", weight_value=rq_cfg.section_weight))
        rq_comp.thresholds.append(RuleThreshold(threshold_key="location_acceptance_min_confidence", threshold_value=rq_cfg.location_acceptance_min_confidence))
        for k, v in rq_cfg.contact_weights.items():
            rq_comp.weights.append(RuleWeight(weight_key=f"contact_{k}", weight_value=v))

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
