from __future__ import annotations
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
        
        from app.models.rules import RuleComponent, SystemRule, RuleCondition, RuleConditionValue, RuleThreshold, RulePenalty, RuleWeight
        
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
        db.flush()

        # 1. Global Tiers
        global_comp = RuleComponent(component_type="global_tiers", component_name="global", profile_id=profile.profile_id)
        db.add(global_comp)
        for tier_name, tier_bounds in config.global_confidence_tiers.items():
            global_comp.thresholds.append(RuleThreshold(threshold_key=f"{tier_name}_min", threshold_value=tier_bounds.min_score))
            global_comp.thresholds.append(RuleThreshold(threshold_key=f"{tier_name}_max", threshold_value=tier_bounds.max_score))
            
        # 2. Fields
        for field_name, field_cfg in config.fields.items():
            field_comp = RuleComponent(component_type="field", component_name=field_name, profile_id=profile.profile_id)
            db.add(field_comp)
            # Thresholds
            field_comp.thresholds.append(RuleThreshold(threshold_key="high_min", threshold_value=field_cfg.tier_thresholds.high_min))
            field_comp.thresholds.append(RuleThreshold(threshold_key="medium_min", threshold_value=field_cfg.tier_thresholds.medium_min))
            field_comp.thresholds.append(RuleThreshold(threshold_key="low_min", threshold_value=field_cfg.tier_thresholds.low_min))
            field_comp.thresholds.append(RuleThreshold(threshold_key="min_acceptance_confidence", threshold_value=field_cfg.downstream_gates.min_acceptance_confidence))
            
            # Downstream gates boolean/int fields stored as thresholds
            if field_cfg.downstream_gates.reject_email_fallback_as_unverified is not None:
                field_comp.thresholds.append(RuleThreshold(threshold_key="reject_email_fallback_as_unverified", threshold_value=1.0 if field_cfg.downstream_gates.reject_email_fallback_as_unverified else 0.0))
            if field_cfg.downstream_gates.max_word_count is not None:
                field_comp.thresholds.append(RuleThreshold(threshold_key="max_word_count", threshold_value=float(field_cfg.downstream_gates.max_word_count)))
            if field_cfg.downstream_gates.max_char_length is not None:
                field_comp.thresholds.append(RuleThreshold(threshold_key="max_char_length", threshold_value=float(field_cfg.downstream_gates.max_char_length)))
            if field_cfg.downstream_gates.require_gazetteer_for_high is not None:
                field_comp.thresholds.append(RuleThreshold(threshold_key="require_gazetteer_for_high", threshold_value=1.0 if field_cfg.downstream_gates.require_gazetteer_for_high else 0.0))

            # Confidence scoring weights
            for k, v in field_cfg.confidence_scoring.items():
                field_comp.weights.append(RuleWeight(weight_key=f"confidence_{k}", weight_value=v))
                
            # Field description stored as a system rule target_value
            desc_rule = SystemRule(rule_type="field_meta", rule_name="description", target_value=field_cfg.description)
            field_comp.system_rules.append(desc_rule)

            # Override reason stored if present
            if field_cfg.tier_thresholds.override_reason:
                or_rule = SystemRule(rule_type="field_meta", rule_name="override_reason", target_value=field_cfg.tier_thresholds.override_reason)
                field_comp.system_rules.append(or_rule)

            # Keywords
            kw_rule = SystemRule(rule_type="keywords", rule_name="field_keywords")
            for k, kw_list in field_cfg.keywords.items():
                cond = RuleCondition(condition_scope=k)
                for kw in kw_list:
                    cond.values.append(RuleConditionValue(value=kw))
                kw_rule.conditions.append(cond)
            field_comp.system_rules.append(kw_rule)

        # 3. Scoring - Match
        match_comp = RuleComponent(component_type="scoring", component_name="match", profile_id=profile.profile_id)
        db.add(match_comp)
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
        
        # Cross Domain Guard penalties
        cdg = match_cfg.cross_domain_guard
        match_comp.penalties.append(RulePenalty(penalty_key="domain_mismatch_multiplier", penalty_value=cdg.domain_mismatch_multiplier))
        match_comp.penalties.append(RulePenalty(penalty_key="domain_mismatch_score_cap", penalty_value=cdg.domain_mismatch_score_cap))
        match_comp.penalties.append(RulePenalty(penalty_key="mandatory_failure_score_impact", penalty_value=cdg.mandatory_failure_score_impact))
        
        # Cross Domain Guard keywords
        cdg_rule = SystemRule(rule_type="cross_domain_guard", rule_name="guard_keywords")
        
        def _add_cdg_cond(scope, keywords):
            cond = RuleCondition(condition_scope=scope)
            for kw in keywords:
                cond.values.append(RuleConditionValue(value=kw))
            cdg_rule.conditions.append(cond)
            
        _add_cdg_cond("software_candidate", cdg.software_candidate_keywords)
        _add_cdg_cond("non_it_job", cdg.non_it_job_keywords)
        _add_cdg_cond("software_requirement", cdg.software_requirement_keywords)
        for domain, kws in cdg.domain_guard_terms.items():
            _add_cdg_cond(f"domain_guard_{domain}", kws)
        match_comp.system_rules.append(cdg_rule)
            
        # Fallback Defaults
        fb = match_cfg.fallback_defaults
        fb_rule = SystemRule(rule_type="fallback_defaults", rule_name="defaults", target_value=f"{fb.recommended_department}::{fb.professional_domain}")
        if fb.suitable_roles:
            role_cond = RuleCondition(condition_scope="suitable_roles")
            for role in fb.suitable_roles:
                role_cond.values.append(RuleConditionValue(value=role))
            fb_rule.conditions.append(role_cond)
        match_comp.system_rules.append(fb_rule)

        # Denylists
        denylist_rule = SystemRule(rule_type="match_denylists", rule_name="denylists")
        for scope, items in [
            ("domain_department_denylist", match_cfg.domain_department_denylist),
            ("cv_section_heading_denylist", match_cfg.cv_section_heading_denylist),
            ("cv_section_heading_compact_denylist", match_cfg.cv_section_heading_compact_denylist),
            ("cv_section_heading_substring_denylist", match_cfg.cv_section_heading_substring_denylist),
        ]:
            if items:
                cond = RuleCondition(condition_scope=scope)
                for item in items:
                    cond.values.append(RuleConditionValue(value=item))
                denylist_rule.conditions.append(cond)
        match_comp.system_rules.append(denylist_rule)

        # Term Matching
        tm = match_cfg.term_matching
        tm_rule = SystemRule(rule_type="term_matching", rule_name="term_matching")
        if tm.stop_phrases:
            sp_cond = RuleCondition(condition_scope="stop_phrases")
            for sp in tm.stop_phrases:
                sp_cond.values.append(RuleConditionValue(value=sp))
            tm_rule.conditions.append(sp_cond)
        if tm.noise_words:
            nw_cond = RuleCondition(condition_scope="noise_words")
            for nw in tm.noise_words:
                nw_cond.values.append(RuleConditionValue(value=nw))
            tm_rule.conditions.append(nw_cond)
        # Aliases stored as scope=alias_{key}, values=alias expansions
        for alias_key, alias_values in tm.aliases.items():
            alias_cond = RuleCondition(condition_scope=f"alias_{alias_key}")
            for av in alias_values:
                alias_cond.values.append(RuleConditionValue(value=av))
            tm_rule.conditions.append(alias_cond)
        match_comp.system_rules.append(tm_rule)

        # Recommendations
        rec = match_cfg.recommendations
        rec_rule = SystemRule(rule_type="recommendations", rule_name="texts", target_value=json.dumps(rec.model_dump()))
        match_comp.system_rules.append(rec_rule)
                        
        # 4. Scoring - Prefilter
        pref_comp = RuleComponent(component_type="scoring", component_name="prefilter", profile_id=profile.profile_id)
        db.add(pref_comp)
        pref_cfg = config.scoring.prefilter
        for k, v in pref_cfg.lexical_weights.model_dump().items():
            if isinstance(v, (int, float)):
                pref_comp.weights.append(RuleWeight(weight_key=k, weight_value=float(v)))
        pref_comp.thresholds.append(RuleThreshold(threshold_key="rrf_k_constant", threshold_value=pref_cfg.rrf_k_constant))
        
        # Prefilter stop words
        pref_rule = SystemRule(rule_type="prefilter", rule_name="stop_words")
        sw_cond = RuleCondition(condition_scope="stop_words")
        for kw in pref_cfg.stop_words:
            sw_cond.values.append(RuleConditionValue(value=kw))
        pref_rule.conditions.append(sw_cond)
        pref_comp.system_rules.append(pref_rule)
        
        # 5. Scoring - Taxonomy
        tax_comp = RuleComponent(component_type="scoring", component_name="taxonomy", profile_id=profile.profile_id)
        db.add(tax_comp)
        tax_cfg = config.scoring.taxonomy
        
        tax_defaults = SystemRule(rule_type="taxonomy_defaults", rule_name="defaults", target_value=f"{tax_cfg.default_domain}::{tax_cfg.default_family}")
        if tax_cfg.canonical_domains:
            cd_cond = RuleCondition(condition_scope="canonical_domains")
            for dom in tax_cfg.canonical_domains:
                cd_cond.values.append(RuleConditionValue(value=dom))
            tax_defaults.conditions.append(cd_cond)
        if tax_cfg.canonical_families:
            cf_cond = RuleCondition(condition_scope="canonical_families")
            for fam in tax_cfg.canonical_families:
                cf_cond.values.append(RuleConditionValue(value=fam))
            tax_defaults.conditions.append(cf_cond)
        tax_comp.system_rules.append(tax_defaults)

        # Compatibility map stored as JSON in a system rule
        if hasattr(tax_cfg, 'compatibility_map') and tax_cfg.compatibility_map:
            compat_rule = SystemRule(rule_type="taxonomy_compatibility", rule_name="compatibility_map", target_value=json.dumps(tax_cfg.compatibility_map))
            tax_comp.system_rules.append(compat_rule)
            
        for vac_rule in tax_cfg.vacancy_rules:
            sys_rule = SystemRule(rule_type="vacancy_taxonomy", rule_name=vac_rule.name, target_value=f"{vac_rule.domain}::{vac_rule.family}")
            for branch in vac_rule.branches:
                for cond in branch.conditions:
                    cond_obj = RuleCondition(
                        condition_scope=cond.scope,
                        condition_mode=cond.mode,
                        is_negated=cond.negate,
                    )
                    for kw in cond.keywords:
                        cond_obj.values.append(RuleConditionValue(value=kw))
                    sys_rule.conditions.append(cond_obj)
            tax_comp.system_rules.append(sys_rule)

        for cand_rule in tax_cfg.candidate_rules:
            sys_rule = SystemRule(rule_type="candidate_taxonomy", rule_name=f"cand_{cand_rule.name}", target_value=f"{cand_rule.domain}::{','.join(cand_rule.families)}")
            for branch in cand_rule.branches:
                for cond in branch.conditions:
                    cond_obj = RuleCondition(
                        condition_scope=cond.scope,
                        condition_mode=cond.mode,
                        is_negated=cond.negate,
                    )
                    for kw in cond.keywords:
                        cond_obj.values.append(RuleConditionValue(value=kw))
                    sys_rule.conditions.append(cond_obj)
            tax_comp.system_rules.append(sys_rule)
                    
        # 6. Scoring - Resume Quality
        rq_comp = RuleComponent(component_type="scoring", component_name="resume_quality", profile_id=profile.profile_id)
        db.add(rq_comp)
        rq_cfg = config.scoring.resume_quality
        rq_comp.weights.append(RuleWeight(weight_key="section_weight", weight_value=rq_cfg.section_weight))
        rq_comp.thresholds.append(RuleThreshold(threshold_key="location_acceptance_min_confidence", threshold_value=rq_cfg.location_acceptance_min_confidence))
        rq_comp.thresholds.append(RuleThreshold(threshold_key="default_density_score", threshold_value=rq_cfg.default_density_score))
        for k, v in rq_cfg.contact_weights.items():
            rq_comp.weights.append(RuleWeight(weight_key=f"contact_{k}", weight_value=v))

        # Core sections
        if rq_cfg.core_sections:
            cs_rule = SystemRule(rule_type="resume_quality_meta", rule_name="core_sections")
            cs_cond = RuleCondition(condition_scope="core_sections")
            for sec in rq_cfg.core_sections:
                cs_cond.values.append(RuleConditionValue(value=sec))
            cs_rule.conditions.append(cs_cond)
            rq_comp.system_rules.append(cs_rule)

        # Section patterns stored as JSON
        if rq_cfg.section_patterns:
            sp_rule = SystemRule(rule_type="resume_quality_meta", rule_name="section_patterns", target_value=json.dumps(rq_cfg.section_patterns))
            rq_comp.system_rules.append(sp_rule)

        # Density scores stored as JSON
        if rq_cfg.density_scores:
            ds_rule = SystemRule(rule_type="resume_quality_meta", rule_name="density_scores", target_value=json.dumps([d.model_dump() for d in rq_cfg.density_scores]))
            rq_comp.system_rules.append(ds_rule)

        # Heading normalization stored as JSON
        if rq_cfg.heading_normalization:
            hn_rule = SystemRule(rule_type="resume_quality_meta", rule_name="heading_normalization", target_value=json.dumps([h.model_dump() for h in rq_cfg.heading_normalization]))
            rq_comp.system_rules.append(hn_rule)

        # 7. Scoring - Domain Embedding
        de_comp = RuleComponent(component_type="scoring", component_name="domain_embedding", profile_id=profile.profile_id)
        db.add(de_comp)
        de_cfg = config.scoring.domain_embedding
        # Categories
        if de_cfg.categories:
            cat_rule = SystemRule(rule_type="domain_embedding_meta", rule_name="categories")
            cat_cond = RuleCondition(condition_scope="categories")
            for cat in de_cfg.categories:
                cat_cond.values.append(RuleConditionValue(value=cat))
            cat_rule.conditions.append(cat_cond)
            de_comp.system_rules.append(cat_rule)
        # Canonical equivalents stored as JSON
        if de_cfg.canonical_equivalents:
            ce_rule = SystemRule(rule_type="domain_embedding_meta", rule_name="canonical_equivalents", target_value=json.dumps(de_cfg.canonical_equivalents))
            de_comp.system_rules.append(ce_rule)

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
        from datetime import datetime, timezone
        
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
        profile_to_activate.activated_at = datetime.now(timezone.utc)
        
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
        from datetime import datetime, timezone
        
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
        profile_to_restore.activated_at = datetime.now(timezone.utc)
        
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
