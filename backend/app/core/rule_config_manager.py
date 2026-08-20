from __future__ import annotations

# backend/app/core/rule_config_manager.py
import hashlib
import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from re import Pattern
from types import MappingProxyType
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger("cv_analyzer")



class GlobalTierBoundary(BaseModel):
    min_score: float = Field(..., ge=0.0, le=1.0)
    max_score: float = Field(..., ge=0.0, le=1.0)


class TierThresholds(BaseModel):
    high_min: float = Field(..., ge=0.0, le=1.0)
    medium_min: float = Field(..., ge=0.0, le=1.0)
    low_min: float = Field(..., ge=0.0, le=1.0)
    override_reason: str | None = None


class DownstreamGates(BaseModel):
    min_acceptance_confidence: float = Field(..., ge=0.0, le=1.0)
    reject_email_fallback_as_unverified: bool = True
    max_word_count: int | None = None
    max_char_length: int | None = None
    require_gazetteer_for_high: bool | None = None


class FieldRuleConfig(BaseModel):
    field_name: str
    description: str
    confidence_scoring: dict[str, float]
    tier_thresholds: TierThresholds
    downstream_gates: DownstreamGates
    keywords: dict[str, list[str]]

    def get_keyword_set(self, key: str) -> set[str]:
        raw_list = self.keywords.get(key, [])
        return {item.lower().strip() for item in raw_list if item}

    def get_upper_keyword_set(self, key: str) -> set[str]:
        raw_list = self.keywords.get(key, [])
        return {item.upper().strip() for item in raw_list if item}


class FallbackDefaults(BaseModel):
    recommended_department: str
    professional_domain: str
    suitable_roles: list[str] = Field(default_factory=list)


class TermMatching(BaseModel):
    stop_phrases: list[str] = Field(default_factory=list)
    noise_words: list[str] = Field(default_factory=list)
    aliases: dict[str, list[str]] = Field(default_factory=dict)


class CrossDomainGuard(BaseModel):
    software_candidate_keywords: list[str] = Field(default_factory=list)
    non_it_job_keywords: list[str] = Field(default_factory=list)
    software_requirement_keywords: list[str] = Field(default_factory=list)
    domain_guard_terms: dict[str, list[str]] = Field(default_factory=dict)
    domain_mismatch_multiplier: float = Field(..., gt=0.0, le=1.0)
    domain_mismatch_score_cap: float = Field(..., gt=0.0)
    mandatory_failure_score_impact: float = Field(..., gt=0.0)


class RecommendationTexts(BaseModel):
    low_coverage: str = Field(
        "Low Confidence Match — Requires HR verification (Vacancy is underspecified).",
        min_length=1,
    )
    high_match: str = Field("Strong candidate — proceed to interview.", min_length=1)
    medium_match: str = Field("Potential match — HR review recommended.", min_length=1)
    low_match: str = Field(
        "Significant requirements missing — Manual HR review required (never auto-rejected).",
        min_length=1,
    )


class ScoringParameters(BaseModel):
    career_transition_role_score: float = Field(..., ge=0.0, le=100.0)
    role_divergence_score: float = Field(..., ge=0.0, le=100.0)
    default_role_score: float = Field(..., ge=0.0, le=100.0)
    below_min_exp_multiplier: float = Field(..., ge=0.0, le=100.0)
    overqualification_penalty: float = Field(..., ge=0.0, le=100.0)
    domain_default_match_score: float = Field(..., ge=0.0, le=100.0)
    low_coverage_threshold: float = Field(..., ge=0.0, le=1.0)
    false_positive_score_cap: float = Field(..., ge=0.0, le=100.0)
    zero_skills_score_cap: float = Field(default=40.0, ge=0.0, le=100.0)
    
    experience_relevance_threshold: float = Field(default=7.0, ge=0.0)
    experience_partial_threshold: float = Field(default=5.5, ge=0.0)
    
    block_weight_taxonomy: float = Field(default=5.0, ge=0.0)
    block_weight_title: float = Field(default=3.0, ge=0.0)
    block_weight_skills: float = Field(default=2.0, ge=0.0)
    
    # Migrated from legacy ConfigRepository
    match_high_threshold: float = Field(..., ge=0.0, le=100.0)
    match_medium_threshold: float = Field(..., ge=0.0, le=100.0)
    mandatory_failure_penalty: float = Field(..., ge=0.0, le=100.0)
    max_score_on_failure: float = Field(..., ge=0.0, le=100.0)
    llm_semantic_weight: float = Field(..., ge=0.0, le=1.0)
    max_llm_boost: float = Field(..., ge=0.0, le=100.0)
    component_weights: dict[str, float] = Field(...)


class MatchScoringRules(BaseModel):
    domain_department_denylist: list[str] = Field(default_factory=list)
    cv_section_heading_denylist: list[str] = Field(default_factory=list)
    cv_section_heading_compact_denylist: list[str] = Field(default_factory=list)
    cv_section_heading_substring_denylist: list[str] = Field(default_factory=list)
    fallback_defaults: FallbackDefaults
    term_matching: TermMatching = Field(default_factory=TermMatching)
    cross_domain_guard: CrossDomainGuard = Field(default_factory=CrossDomainGuard)
    recommendations: RecommendationTexts = Field(default_factory=RecommendationTexts)
    scoring_parameters: ScoringParameters = Field(default_factory=ScoringParameters)


class LexicalWeights(BaseModel):
    department_match: float = Field(..., ge=0.0)
    title_term_match: float = Field(..., ge=0.0)
    required_skill_match: float = Field(..., ge=0.0)
    preferred_keyword_match: float = Field(..., ge=0.0)
    experience_suitability: float = Field(..., ge=0.0)


class PrefilterRules(BaseModel):
    stop_words: list[str] = Field(default_factory=list)
    lexical_weights: LexicalWeights
    rrf_k_constant: float = Field(..., gt=0.0)


class TaxonomyCondition(BaseModel):
    scope: Literal["title", "dept", "full_text", "candidate_full_text"]
    keywords: list[str] = Field(default_factory=list)
    mode: Literal["any", "all"] = "any"
    negate: bool = False


class TaxonomyRuleBranch(BaseModel):
    conditions: list[TaxonomyCondition] = Field(default_factory=list)


class VacancyTaxonomyRule(BaseModel):
    name: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    family: str = Field(..., min_length=1)
    branches: list[TaxonomyRuleBranch] = Field(default_factory=list)


class CandidateTaxonomyRule(BaseModel):
    name: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    families: list[str] = Field(default_factory=list)
    branches: list[TaxonomyRuleBranch] = Field(default_factory=list)


class TaxonomyRules(BaseModel):
    canonical_domains: list[str] = Field(default_factory=list)
    canonical_families: list[str] = Field(default_factory=list)
    default_domain: str = Field(..., min_length=1)
    default_family: str = Field(..., min_length=1)
    vacancy_rules: list[VacancyTaxonomyRule] = Field(default_factory=list)
    candidate_rules: list[CandidateTaxonomyRule] = Field(default_factory=list)
    
    evidence_weight_experience: float = Field(default=5.0, ge=0.0)
    evidence_weight_responsibilities: float = Field(default=3.0, ge=0.0)
    evidence_weight_skills: float = Field(default=2.0, ge=0.0)
    evidence_weight_summary: float = Field(default=1.5, ge=0.0)
    evidence_weight_education: float = Field(default=1.0, ge=0.0)
    semantic_match_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    main_department_match_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    hierarchy_ambiguity_gap: float = Field(default=0.05, ge=0.0, le=1.0)
    hierarchy_ambiguity_candidate_min_score: float = Field(default=0.35, ge=0.0, le=1.0)
    hierarchy_exact_name_score: float = Field(default=0.60, ge=0.0, le=1.0)
    hierarchy_normalized_name_score: float = Field(default=0.40, ge=0.0, le=1.0)
    hierarchy_role_keyword_score: float = Field(default=0.25, ge=0.0, le=1.0)
    hierarchy_domain_keyword_score: float = Field(default=0.20, ge=0.0, le=1.0)
    hierarchy_skill_keyword_score: float = Field(default=0.15, ge=0.0, le=1.0)
    hierarchy_cv_keyword_score: float = Field(default=0.10, ge=0.0, le=1.0)
    hierarchy_rule_score_cap: float = Field(default=0.80, ge=0.0, le=1.0)
    family_compatibility_min_score: float = Field(default=0.40, ge=0.0, le=1.0)
    normalizer_partial_match_confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class DensityScoreTier(BaseModel):
    min_words_per_page: int = Field(..., ge=0)
    score: float = Field(..., ge=0.0, le=1.0)


class HeadingNormalization(BaseModel):
    pattern: str = Field(..., min_length=1)
    replacement: str = Field(..., min_length=1)


class ResumeQualityRules(BaseModel):
    section_patterns: dict[str, str] = Field(default_factory=dict)
    core_sections: list[str] = Field(default_factory=list)
    section_weight: float = Field(..., ge=0.0, le=1.0)
    contact_weights: dict[str, float] = Field(...)
    location_acceptance_min_confidence: float = Field(..., ge=0.0, le=1.0)
    density_scores: list[DensityScoreTier] = Field(default_factory=list)
    default_density_score: float = Field(..., ge=0.0, le=1.0)
    heading_normalization: list[HeadingNormalization] = Field(default_factory=list)


class DomainEmbeddingRules(BaseModel):
    categories: list[str] = Field(default_factory=list)
    canonical_equivalents: dict[str, dict[str, str]] = Field(default_factory=dict)
    semantic_equivalence_threshold: float = Field(default=0.82, ge=0.0, le=1.0)
    max_equivalents: int = Field(default=5, ge=1)


class WorkflowRules(BaseModel):
    allowed_job_states: list[str] = Field(
        default_factory=lambda: ["QUEUED", "PROCESSING", "RETRYING", "COMPLETED", "COMPLETED_DEGRADED", "FAILED", "CANCELLED", "UNKNOWN"]
    )
    job_state_transitions: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "QUEUED": ["QUEUED", "PROCESSING", "RETRYING", "FAILED", "CANCELLED"],
            "PROCESSING": ["PROCESSING", "RETRYING", "COMPLETED", "COMPLETED_DEGRADED", "FAILED", "CANCELLED"],
            "RETRYING": ["RETRYING", "PROCESSING", "FAILED", "CANCELLED"],
            "COMPLETED": ["COMPLETED", "QUEUED"],
            "COMPLETED_DEGRADED": ["COMPLETED_DEGRADED", "QUEUED"],
            "FAILED": ["FAILED", "QUEUED"],
            "CANCELLED": ["CANCELLED", "QUEUED"],
            "UNKNOWN": ["QUEUED", "FAILED"],
        }
    )

    @model_validator(mode="after")
    def include_persistence_degraded_state(self) -> "WorkflowRules":
        """Upgrade stored workflow configurations created before degraded completion existed."""
        if "COMPLETED_DEGRADED" not in self.allowed_job_states:
            self.allowed_job_states.append("COMPLETED_DEGRADED")
        processing_targets = self.job_state_transitions.setdefault("PROCESSING", [])
        if "COMPLETED_DEGRADED" not in processing_targets:
            processing_targets.append("COMPLETED_DEGRADED")
        self.job_state_transitions.setdefault("COMPLETED_DEGRADED", ["COMPLETED_DEGRADED", "QUEUED"])
        if "CANCELLED" not in self.allowed_job_states:
            self.allowed_job_states.append("CANCELLED")
        for state in ("QUEUED", "PROCESSING", "RETRYING"):
            targets = self.job_state_transitions.setdefault(state, [])
            if "CANCELLED" not in targets:
                targets.append("CANCELLED")
        self.job_state_transitions.setdefault("CANCELLED", ["CANCELLED", "QUEUED"])
        return self


class ScoringRules(BaseModel):
    match: MatchScoringRules
    prefilter: PrefilterRules
    taxonomy: TaxonomyRules
    resume_quality: ResumeQualityRules
    domain_embedding: DomainEmbeddingRules

class HiringRiskPolicy(BaseModel):
    enabled: bool = True
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]
    manual_review: bool
    category: str = "Requirements"
    title: str | None = None
    source: str | None = None

class HiringRiskConfig(BaseModel):
    policies: dict[str, HiringRiskPolicy] = Field(default_factory=dict)


class UnifiedRuleConfig(BaseModel):
    version: str
    description: str
    last_updated: str
    schema_version: str = "v1.0"
    policy_version: str = "v2026.1"
    effective_from: str = ""
    source: str = "DATABASE"
    degraded_mode: bool = False
    changed_by: str = "system.admin@cv-analyzer.enterprise"
    change_reason: str = "Bootstrap configuration snapshot"
    global_confidence_tiers: dict[str, GlobalTierBoundary]
    fields: dict[str, FieldRuleConfig]
    scoring: ScoringRules
    workflow: WorkflowRules = Field(default_factory=WorkflowRules)
    hiring_risks: HiringRiskConfig = Field(default_factory=HiringRiskConfig)

    @model_validator(mode="after")
    def validate_safety_invariants(self) -> "UnifiedRuleConfig":
        """Enforces critical safety gates to prevent silent misconfigurations."""
        name_cfg = self.fields.get("name")
        if name_cfg:
            min_acc = name_cfg.downstream_gates.min_acceptance_confidence
            email_fb = name_cfg.confidence_scoring.get("email_username_fallback", 0.0)
            if min_acc <= email_fb:
                raise ValueError("[SAFETY_GATE_VIOLATION] min_acceptance_confidence must be strictly greater than email_username_fallback")

        for field_name, cfg in self.fields.items():
            if cfg.tier_thresholds.override_reason is None and (cfg.tier_thresholds.high_min != 0.80 or cfg.tier_thresholds.medium_min != 0.50):
                raise ValueError(f"[SAFETY_GATE_VIOLATION] Field '{field_name}' tier threshold modified but override_reason is missing")

            if cfg.downstream_gates.min_acceptance_confidence < cfg.tier_thresholds.medium_min:
                raise ValueError(f"[SAFETY_GATE_VIOLATION] Field '{field_name}' min_acceptance_confidence cannot be lower than medium_min threshold")

        loc = self.fields.get("location")
        if loc:
            blacklist = loc.get_keyword_set("blacklist")
            if not blacklist:
                logger.warning("[SAFETY_GATE_WARN] Location field blacklist is empty")

        comp = self.fields.get("company_name")
        if comp:
            generic = comp.get_keyword_set("generic_section_headers")
            if not generic:
                logger.warning("[SAFETY_GATE_WARN] Company name generic_section_headers is empty")
            if not comp.get_keyword_set("suffixes"):
                raise ValueError("[SAFETY_GATE_VIOLATION] Company name suffixes missing. Cannot parse organizations without config.")

        title = self.fields.get("job_title")
        if title:
            starters = title.get_keyword_set("narrative_starters")
            if not starters:
                logger.warning("[SAFETY_GATE_WARN] Job title narrative_starters is empty")
            if not title.get_upper_keyword_set("keywords"):
                raise ValueError("[SAFETY_GATE_VIOLATION] Job title keywords missing. Cannot parse roles without config.")

        match_rules = self.scoring.match
        guard = match_rules.cross_domain_guard
        if not guard.software_candidate_keywords:
            raise ValueError("[SAFETY_GATE_VIOLATION] scoring.match.cross_domain_guard.software_candidate_keywords must not be empty")

        if not guard.non_it_job_keywords:
            raise ValueError("[SAFETY_GATE_VIOLATION] scoring.match.cross_domain_guard.non_it_job_keywords must not be empty")

        taxonomy = self.scoring.taxonomy
        if not taxonomy.vacancy_rules:
            raise ValueError("[SAFETY_GATE_VIOLATION] scoring.taxonomy.vacancy_rules must not be empty")
        if not taxonomy.candidate_rules:
            raise ValueError("[SAFETY_GATE_VIOLATION] scoring.taxonomy.candidate_rules must not be empty")
        # Canonical family checks
        if taxonomy.default_family not in taxonomy.canonical_families:
            raise ValueError(f"[SAFETY_GATE_VIOLATION] scoring.taxonomy.default_family '{taxonomy.default_family}' must be in canonical_families")

        canonical_d = set(taxonomy.canonical_domains)
        for rule in taxonomy.vacancy_rules:
            if rule.domain not in canonical_d:
                raise ValueError(f"[SAFETY_GATE_VIOLATION] Taxonomy vacancy_rules contains unknown domain '{rule.domain}'")

        resume_quality = self.scoring.resume_quality
        if not resume_quality.section_patterns:
            raise ValueError("[SAFETY_GATE_VIOLATION] scoring.resume_quality.section_patterns must not be empty")

        density = resume_quality.density_scores
        for i in range(len(density) - 1):
            if density[i].min_words_per_page <= density[i + 1].min_words_per_page:
                raise ValueError("[SAFETY_GATE_VIOLATION] Resume quality density_scores must be ordered by descending min_words_per_page")

        domain_embedding = self.scoring.domain_embedding
        if not domain_embedding.categories:
            raise ValueError("[SAFETY_GATE_VIOLATION] scoring.domain_embedding.categories must not be empty")

        return self


class RuleConfigManager:
    """
    Thread-safe enterprise rule configuration manager with startup cache warming,
    immutable precompiled assets, telemetry diagnostics, and atomic hot-reload.
    """

    _lock = threading.RLock()
    _active_configs: dict[str, UnifiedRuleConfig] = {}
    _load_counter: int = 0
    _caches: dict[str, MappingProxyType] = {}
    _metrics: MappingProxyType = MappingProxyType({})

    @classmethod
    def is_config_loaded(cls, tenant_id: str | None = None) -> bool:
        """Return whether a validated configuration is active in this process."""
        tenant_key = tenant_id or "GLOBAL"
        with cls._lock:
            return tenant_key in cls._active_configs

    @classmethod
    def load_config(
        cls,
        tenant_id: str | None = None,
    ) -> UnifiedRuleConfig:
        """Load, validate, warm all caches, and atomically activate a rule configuration from PostgreSQL."""
        t0 = time.perf_counter()

        raw_data = None
        path_hash: str | None = None
        config_size_bytes = 0

        try:
            from sqlalchemy.orm import selectinload

            from app.core.database import PostgresAppSession
            from app.models.rules import RuleComponent, RuleCondition, RuleConfigProfile, SystemRule
            
            with PostgresAppSession() as db:
                query = db.query(RuleConfigProfile).options(
                    selectinload(RuleConfigProfile.components).selectinload(RuleComponent.system_rules).selectinload(SystemRule.conditions).selectinload(RuleCondition.values),
                    selectinload(RuleConfigProfile.components).selectinload(RuleComponent.thresholds),
                    selectinload(RuleConfigProfile.components).selectinload(RuleComponent.penalties),
                    selectinload(RuleConfigProfile.components).selectinload(RuleComponent.weights),
                ).filter(RuleConfigProfile.is_active == True)
                if tenant_id:
                    query = query.filter(RuleConfigProfile.tenant_id == tenant_id)
                else:
                    query = query.filter(RuleConfigProfile.tenant_id.is_(None))
                active_profile = query.first()
                if active_profile:
                    raw_data = cls._hydrate_profile(active_profile)
                    raw_data["source"] = "DATABASE"
                    raw_data["degraded_mode"] = False
                    path_hash = active_profile.version_tag
                    config_size_bytes = len(json.dumps(raw_data))
                    logger.info(f"[RULE_CONFIG] Hydrated active profile from database (v{active_profile.version_tag})")
                    
                    from app.core.cache import config_cache_manager
                    cache_key = f"rule_config_profile_{tenant_id or 'GLOBAL'}"
                    config_cache_manager.set(cache_key, raw_data)
        except Exception as e:
            logger.error(f"[RULE_CONFIG] Failed to load config from database: {e}")

        if raw_data is None:
            # Check cache as a fallback for intermittent DB issues if cache is populated
            from app.core.cache import config_cache_manager
            cache_key = f"rule_config_profile_{tenant_id or 'GLOBAL'}"
            cached_data = config_cache_manager.get(cache_key)
            if cached_data:
                raw_data = dict(cached_data)
                raw_data["source"] = "bundled_static"
                raw_data["degraded_mode"] = True
                path_hash = cached_data.get("version", "cached")
                config_size_bytes = len(json.dumps(raw_data))
                logger.info(f"[RULE_CONFIG] Loading active profile from fallback cache (v{path_hash}) in degraded_mode")
            else:
                from app.services.system_rule_config_factory import SystemRuleConfigFactory
                raw_data = SystemRuleConfigFactory.build().model_dump()
                raw_data["source"] = "bundled_static"
                raw_data["degraded_mode"] = True
                path_hash = raw_data.get("version", "static_fallback")
                config_size_bytes = len(json.dumps(raw_data))
                logger.warning("[RULE_CONFIG] Database and cache unavailable; loaded bundled_static baseline fallback in degraded_mode")

        if raw_data is None:
            from app.core.error_handlers import SystemConfigurationError
            raise SystemConfigurationError("CONFIGURATION_UNAVAILABLE")

        # 1. Pydantic Model & Safety Invariants Validation
        candidate_config = UnifiedRuleConfig.model_validate(raw_data)

        # 2. In-Memory Synthetic Smoke Test Suite
        cls._run_synthetic_smoke_tests(candidate_config)

        # 3. Startup Cache Warming & Regex Precompilation
        t_cache_0 = time.perf_counter()
        candidate_cache, compiled_pattern_count = cls._build_and_validate_all_caches(candidate_config)
        cache_build_time_ms = round((time.perf_counter() - t_cache_0) * 1000.0, 2)
        total_load_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        # 4. Atomic Thread-Safe Swap
        with cls._lock:
            tenant_key = tenant_id or 'GLOBAL'
            cls._active_configs[tenant_key] = candidate_config
            cls._caches[tenant_key] = candidate_cache
            cls._load_counter += 1
            cls._metrics = MappingProxyType(
                {
                    "config_version": candidate_config.version,
                    "config_load_count": cls._load_counter,
                    "config_load_time_ms": total_load_time_ms,
                    "cache_build_time_ms": cache_build_time_ms,
                    "compiled_pattern_count": compiled_pattern_count,
                    "configuration_size_bytes": config_size_bytes,
                    "last_loaded_timestamp": datetime.now(timezone.utc).isoformat(),
                    "file_hash": path_hash,
                }
            )

        logger.info(
            f"[RULE_CONFIG] Successfully loaded and activated rule_config "
            f"v{candidate_config.version} ({len(candidate_config.fields)} fields configured) | "
            f"LoadTime={total_load_time_ms}ms, CacheTime={cache_build_time_ms}ms, CompiledPatterns={compiled_pattern_count}"
        )
        return cls._active_configs[tenant_key]

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all active in-memory configuration caches."""
        with cls._lock:
            cls._active_configs.clear()
            cls._caches.clear()
            try:
                from app.core.cache import config_cache_manager
                config_cache_manager.clear()
            except Exception:
                pass

    @classmethod
    def _hydrate_profile(cls, profile) -> dict[str, Any]:
        """Convert normalized DB rows back to UnifiedRuleConfig JSON structure."""
        
        base_dict: dict[str, Any] = {}

        base_dict["version"] = profile.version_tag
        base_dict["description"] = profile.description or ""
        base_dict["last_updated"] = profile.updated_at.isoformat()
        
        for comp in profile.components:
            if comp.component_type == "global_tiers":
                if "global_confidence_tiers" not in base_dict:
                    base_dict["global_confidence_tiers"] = {}
                    
                tier_names = {t.threshold_key.replace("_min", "").replace("_max", "") for t in comp.thresholds}
                for t_name in tier_names:
                    min_val = next((t.threshold_value for t in comp.thresholds if t.threshold_key == f"{t_name}_min"), 0.0)
                    max_val = next((t.threshold_value for t in comp.thresholds if t.threshold_key == f"{t_name}_max"), 1.0)
                    base_dict["global_confidence_tiers"][t_name] = {"min_score": min_val, "max_score": max_val}
                    
            elif comp.component_type == "field":
                if "fields" not in base_dict:
                    base_dict["fields"] = {}
                f_name = comp.component_name
                
                field_dict: dict[str, Any] = {
                    "field_name": f_name,
                    "description": "",
                    "confidence_scoring": {},
                    "tier_thresholds": {},
                    "downstream_gates": {},
                    "keywords": {}
                }

                # Thresholds → tier_thresholds and downstream_gates
                tier_keys = {"high_min", "medium_min", "low_min"}
                gate_threshold_key = "min_acceptance_confidence"
                gate_bool_keys = {"reject_email_fallback_as_unverified", "require_gazetteer_for_high"}
                gate_int_keys = {"max_word_count", "max_char_length"}

                for t in comp.thresholds:
                    if t.threshold_key in tier_keys:
                        field_dict["tier_thresholds"][t.threshold_key] = t.threshold_value
                    elif t.threshold_key == gate_threshold_key:
                        field_dict["downstream_gates"][t.threshold_key] = t.threshold_value
                    elif t.threshold_key in gate_bool_keys:
                        field_dict["downstream_gates"][t.threshold_key] = t.threshold_value >= 0.5
                    elif t.threshold_key in gate_int_keys:
                        field_dict["downstream_gates"][t.threshold_key] = int(t.threshold_value)

                # Weights → confidence_scoring
                for w in comp.weights:
                    if w.weight_key.startswith("confidence_"):
                        field_dict["confidence_scoring"][w.weight_key.replace("confidence_", "")] = w.weight_value
                        
                # System rules → keywords, description, override_reason
                for r in comp.system_rules:
                    if r.rule_type == "keywords":
                        for c in r.conditions:
                            field_dict["keywords"][c.condition_scope] = [v.value for v in c.values]
                    elif r.rule_type == "field_meta":
                        if r.rule_name == "description" and r.target_value:
                            field_dict["description"] = r.target_value
                        elif r.rule_name == "override_reason" and r.target_value:
                            field_dict["tier_thresholds"]["override_reason"] = r.target_value
                            
                base_dict["fields"][f_name] = field_dict
                
            elif comp.component_type == "scoring":
                if "scoring" not in base_dict:
                    base_dict["scoring"] = {}
                    
                c_name = comp.component_name
                
                if c_name == "match":
                    match_dict: dict[str, Any] = base_dict["scoring"].get("match", {})
                    if "scoring_parameters" not in match_dict:
                        match_dict["scoring_parameters"] = {}
                    
                    # Weights → scoring_parameters + component_weights
                    comp_weights: dict[str, float] = {}
                    for w in comp.weights:
                        if w.weight_key.startswith("component_weights_"):
                            comp_weights[w.weight_key.replace("component_weights_", "")] = w.weight_value
                        else:
                            match_dict["scoring_parameters"][w.weight_key] = w.weight_value
                    if comp_weights:
                        match_dict["scoring_parameters"]["component_weights"] = comp_weights

                    # Thresholds → scoring_parameters
                    for t in comp.thresholds:
                        match_dict["scoring_parameters"][t.threshold_key] = t.threshold_value
                    
                    # Penalties → cross_domain_guard or scoring_parameters
                    for p in comp.penalties:
                        if p.penalty_key in ("domain_mismatch_multiplier", "domain_mismatch_score_cap", "mandatory_failure_score_impact"):
                            if "cross_domain_guard" not in match_dict:
                                match_dict["cross_domain_guard"] = {}
                            match_dict["cross_domain_guard"][p.penalty_key] = p.penalty_value
                        else:
                            match_dict["scoring_parameters"][p.penalty_key] = p.penalty_value

                    # System rules
                    for r in comp.system_rules:
                        if r.rule_type == "cross_domain_guard":
                            cdg = match_dict.get("cross_domain_guard", {})
                            if "domain_guard_terms" not in cdg:
                                cdg["domain_guard_terms"] = {}
                            for c in r.conditions:
                                kws = [v.value for v in c.values]
                                if c.condition_scope == "software_candidate":
                                    cdg["software_candidate_keywords"] = kws
                                elif c.condition_scope == "non_it_job":
                                    cdg["non_it_job_keywords"] = kws
                                elif c.condition_scope == "software_requirement":
                                    cdg["software_requirement_keywords"] = kws
                                elif c.condition_scope.startswith("domain_guard_"):
                                    cdg["domain_guard_terms"][c.condition_scope.replace("domain_guard_", "")] = kws
                            match_dict["cross_domain_guard"] = cdg

                        elif r.rule_type == "fallback_defaults":
                            parts = (r.target_value or "::").split("::")
                            fb: dict[str, Any] = {
                                "recommended_department": parts[0] if parts else "",
                                "professional_domain": parts[1] if len(parts) > 1 else "",
                                "suitable_roles": [],
                            }
                            for c in r.conditions:
                                if c.condition_scope == "suitable_roles":
                                    fb["suitable_roles"] = [v.value for v in c.values]
                            match_dict["fallback_defaults"] = fb

                        elif r.rule_type == "match_denylists":
                            for c in r.conditions:
                                match_dict[c.condition_scope] = [v.value for v in c.values]

                        elif r.rule_type == "term_matching":
                            tm: dict[str, Any] = {"stop_phrases": [], "noise_words": [], "aliases": {}}
                            for c in r.conditions:
                                if c.condition_scope == "stop_phrases":
                                    tm["stop_phrases"] = [v.value for v in c.values]
                                elif c.condition_scope == "noise_words":
                                    tm["noise_words"] = [v.value for v in c.values]
                                elif c.condition_scope.startswith("alias_"):
                                    alias_key = c.condition_scope.replace("alias_", "")
                                    tm["aliases"][alias_key] = [v.value for v in c.values]
                            match_dict["term_matching"] = tm

                        elif r.rule_type == "recommendations":
                            if r.target_value:
                                match_dict["recommendations"] = json.loads(r.target_value)

                    base_dict["scoring"]["match"] = match_dict
                    
                elif c_name == "prefilter":
                    pref_dict: dict[str, Any] = base_dict["scoring"].get("prefilter", {})
                    if "lexical_weights" not in pref_dict:
                        pref_dict["lexical_weights"] = {}
                    for w in comp.weights:
                        pref_dict["lexical_weights"][w.weight_key] = w.weight_value
                    for t in comp.thresholds:
                        if t.threshold_key == "rrf_k_constant":
                            pref_dict["rrf_k_constant"] = t.threshold_value
                    for r in comp.system_rules:
                        if r.rule_type == "prefilter" and r.rule_name == "stop_words":
                            for c in r.conditions:
                                if c.condition_scope == "stop_words":
                                    pref_dict["stop_words"] = [v.value for v in c.values]
                    base_dict["scoring"]["prefilter"] = pref_dict
                    
                elif c_name == "taxonomy":
                    tax_dict: dict[str, Any] = base_dict["scoring"].get("taxonomy", {})
                    for weight in comp.weights:
                        tax_dict[weight.weight_key] = weight.weight_value
                    for threshold in comp.thresholds:
                        tax_dict[threshold.threshold_key] = threshold.threshold_value
                    vac_rules = []
                    cand_rules = []
                    for r in comp.system_rules:
                        if r.rule_type == "taxonomy_defaults":
                            parts = (r.target_value or "::").split("::")
                            tax_dict["default_domain"] = parts[0] if parts else "General Operations"
                            tax_dict["default_family"] = parts[1] if len(parts) > 1 else "General Professional"
                            for c in r.conditions:
                                if c.condition_scope == "canonical_domains":
                                    tax_dict["canonical_domains"] = [v.value for v in c.values]
                                elif c.condition_scope == "canonical_families":
                                    tax_dict["canonical_families"] = [v.value for v in c.values]

                        elif r.rule_type == "taxonomy_compatibility":
                            if r.target_value:
                                tax_dict["compatibility_map"] = json.loads(r.target_value)

                        elif r.rule_type in ("vacancy_taxonomy", "candidate_taxonomy"):
                            if not r.target_value:
                                continue
                            parts = r.target_value.split("::")
                            domain = parts[0]
                            families = parts[1].split(",") if len(parts) > 1 else []
                            
                            rule_name = r.rule_name
                            if r.rule_type == "candidate_taxonomy" and rule_name.startswith("cand_"):
                                rule_name = rule_name[5:]
                            rule_obj: dict[str, Any] = {
                                "name": rule_name,
                                "domain": domain,
                                "branches": [],
                            }
                            branches: dict[int, list[dict[str, Any]]] = {}
                            for c in r.conditions:
                                branch_index = getattr(c, "branch_index", 0)
                                branches.setdefault(branch_index, []).append({
                                    "scope": c.condition_scope,
                                    "mode": c.condition_mode,
                                    "negate": c.is_negated,
                                    "keywords": [v.value for v in c.values]
                                })
                            rule_obj["branches"] = [
                                {"conditions": conditions}
                                for _, conditions in sorted(branches.items())
                            ]
                                
                            if r.rule_type == "vacancy_taxonomy":
                                rule_obj["family"] = families[0] if families else ""
                                vac_rules.append(rule_obj)
                            elif r.rule_type == "candidate_taxonomy":
                                rule_obj["families"] = families
                                cand_rules.append(rule_obj)

                    tax_dict["vacancy_rules"] = vac_rules
                    tax_dict["candidate_rules"] = cand_rules
                    base_dict["scoring"]["taxonomy"] = tax_dict
                    
                elif c_name == "resume_quality":
                    rq_dict: dict[str, Any] = base_dict["scoring"].get("resume_quality", {})
                    if "contact_weights" not in rq_dict:
                        rq_dict["contact_weights"] = {}
                    for w in comp.weights:
                        if w.weight_key == "section_weight":
                            rq_dict["section_weight"] = w.weight_value
                        elif w.weight_key.startswith("contact_"):
                            rq_dict["contact_weights"][w.weight_key.replace("contact_", "")] = w.weight_value
                    for t in comp.thresholds:
                        rq_dict[t.threshold_key] = t.threshold_value

                    for r in comp.system_rules:
                        if r.rule_type == "resume_quality_meta":
                            if r.rule_name == "core_sections":
                                for c in r.conditions:
                                    if c.condition_scope == "core_sections":
                                        rq_dict["core_sections"] = [v.value for v in c.values]
                            elif r.rule_name == "section_patterns" and r.target_value:
                                rq_dict["section_patterns"] = json.loads(r.target_value)
                            elif r.rule_name == "density_scores" and r.target_value:
                                rq_dict["density_scores"] = json.loads(r.target_value)
                            elif r.rule_name == "heading_normalization" and r.target_value:
                                rq_dict["heading_normalization"] = json.loads(r.target_value)

                    base_dict["scoring"]["resume_quality"] = rq_dict

                elif c_name == "domain_embedding":
                    de_dict: dict[str, Any] = base_dict["scoring"].get("domain_embedding", {})
                    for r in comp.system_rules:
                        if r.rule_type == "domain_embedding_meta":
                            if r.rule_name == "categories":
                                for c in r.conditions:
                                    if c.condition_scope == "categories":
                                        de_dict["categories"] = [v.value for v in c.values]
                            elif r.rule_name == "canonical_equivalents" and r.target_value:
                                de_dict["canonical_equivalents"] = json.loads(r.target_value)
                    base_dict["scoring"]["domain_embedding"] = de_dict

            elif comp.component_type == "workflow":
                workflow_rule = next(
                    (
                        rule
                        for rule in comp.system_rules
                        if rule.rule_type == "workflow_state_machine" and rule.rule_name == "job_states" and rule.target_value
                    ),
                    None,
                )
                if workflow_rule:
                    base_dict["workflow"] = json.loads(workflow_rule.target_value)

            elif comp.component_type == "hiring_risks":
                policies: dict[str, Any] = {}
                for rule in comp.system_rules:
                    if rule.rule_type != "hiring_risk_policy" or not rule.target_value:
                        continue
                    policy = json.loads(rule.target_value)
                    if not isinstance(policy, dict):
                        raise ValueError(f"Hiring Risk policy '{rule.rule_name}' must be a JSON object.")
                    policies[rule.rule_name] = policy
                base_dict["hiring_risks"] = {"policies": policies}

        return base_dict


    @classmethod
    def _build_and_validate_all_caches(cls, config: UnifiedRuleConfig) -> tuple[MappingProxyType, int]:
        """Pre-compiles and warms ALL regexes and immutable asset dictionaries at startup."""
        pattern_count = 0

        # A. Term Matching
        tm = config.scoring.match.term_matching
        term_matching_assets = MappingProxyType(
            {
                "stop_phrases": frozenset(p.lower().strip() for p in tm.stop_phrases if p),
                "noise_words": frozenset(w.lower().strip() for w in tm.noise_words if w),
                "aliases": MappingProxyType({k.lower().strip(): [a.lower().strip() for a in v if a] for k, v in tm.aliases.items() if k and k.strip()}),
            }
        )

        # B. Cross Domain Guard Sets
        guard = config.scoring.match.cross_domain_guard
        cross_domain_assets = MappingProxyType(
            {
                "software_candidate_keywords": frozenset(k.lower().strip() for k in guard.software_candidate_keywords if k),
                "non_it_job_keywords": frozenset(k.lower().strip() for k in guard.non_it_job_keywords if k),
                "software_requirement_keywords": frozenset(k.lower().strip() for k in guard.software_requirement_keywords if k),
                "domain_guard_terms": MappingProxyType({domain.lower().strip(): frozenset(k.lower().strip() for k in keywords if k) for domain, keywords in guard.domain_guard_terms.items()}),
            }
        )

        # C. Resume Quality Section Patterns & Heading Normalizations
        rq = config.scoring.resume_quality
        section_patterns = {}
        for name, pattern in rq.section_patterns.items():
            section_patterns[name] = re.compile(pattern, re.IGNORECASE)
            pattern_count += 1

        heading_normalizations = []
        for h in rq.heading_normalization:
            heading_normalizations.append((re.compile(h.pattern, re.IGNORECASE), h.replacement))
            pattern_count += 1

        compiled_rq = MappingProxyType(
            {
                "section_patterns": MappingProxyType(section_patterns),
                "heading_normalization": tuple(heading_normalizations),
            }
        )

        # D. Compiled Cross Domain Guard Regexes
        soft_cand_p = tuple(re.compile(r"\b" + re.escape(k.lower().strip()) + r"\b", re.IGNORECASE) for k in guard.software_candidate_keywords if k and k.strip())
        pattern_count += len(soft_cand_p)

        non_it_p = tuple(re.compile(r"\b" + re.escape(k.lower().strip()) + r"\b", re.IGNORECASE) for k in guard.non_it_job_keywords if k and k.strip())
        pattern_count += len(non_it_p)

        soft_req_p = tuple(re.compile(r"\b" + re.escape(k.lower().strip()) + r"\b", re.IGNORECASE) for k in guard.software_requirement_keywords if k and k.strip())
        pattern_count += len(soft_req_p)

        domain_guard_map = {}
        for domain, keywords in guard.domain_guard_terms.items():
            compiled_terms = tuple(re.compile(r"\b" + re.escape(k.lower().strip()) + r"\b", re.IGNORECASE) for k in keywords if k and k.strip())
            domain_guard_map[domain.lower().strip()] = compiled_terms
            pattern_count += len(compiled_terms)

        compiled_cross_domain_guard = MappingProxyType(
            {
                "software_candidate_patterns": soft_cand_p,
                "non_it_job_patterns": non_it_p,
                "software_requirement_patterns": soft_req_p,
                "domain_guard_term_patterns": MappingProxyType(domain_guard_map),
            }
        )

        # Cache Validation Gate
        if pattern_count == 0:
            raise ValueError("[CACHE_VALIDATION_FAILURE] Compiled pattern count must be > 0")
        if not section_patterns:
            raise ValueError("[CACHE_VALIDATION_FAILURE] Section patterns map is empty")
        if not soft_cand_p:
            raise ValueError("[CACHE_VALIDATION_FAILURE] Software candidate patterns are empty")

        cache_dict = MappingProxyType(
            {
                "config": config,
                "term_matching": term_matching_assets,
                "cross_domain_guard": cross_domain_assets,
                "compiled": compiled_rq,
                "compiled_cross_domain_guard": compiled_cross_domain_guard,
                "recommendations": config.scoring.match.recommendations,
                "scoring_parameters": config.scoring.match.scoring_parameters,
            }
        )
        return cache_dict, pattern_count

    @classmethod
    def get_metrics(cls) -> dict[str, Any]:
        """Exposes lightweight diagnostics and telemetry metrics."""
        with cls._lock:
            if not cls._active_configs:
                cls.load_config()
            return dict(cls._metrics)

    @classmethod
    def get_config(cls, tenant_id: str | None = None) -> UnifiedRuleConfig:
        with cls._lock:
            tenant_key = tenant_id or 'GLOBAL'
        if tenant_key not in cls._active_configs:
            cls.load_config(tenant_id=tenant_id)
        return cls._active_configs[tenant_key]

    @classmethod
    def get_field_config(cls, field_name: str, tenant_id: str | None = None) -> FieldRuleConfig:
        cfg = cls.get_config(tenant_id=tenant_id)
        if field_name not in cfg.fields:
            raise KeyError(f"Field '{field_name}' not configured in UnifiedRuleConfig")
        return cfg.fields[field_name]

    @classmethod
    def get_keywords(cls, field_name: str, key: str, tenant_id: str | None = None) -> set[str]:
        try:
            field_cfg = cls.get_field_config(field_name, tenant_id=tenant_id)
            return field_cfg.get_keyword_set(key)
        except Exception:
            return set()

    @classmethod
    def get_upper_keywords(cls, field_name: str, key: str, tenant_id: str | None = None) -> set[str]:
        try:
            field_cfg = cls.get_field_config(field_name, tenant_id=tenant_id)
            return field_cfg.get_upper_keyword_set(key)
        except Exception:
            return set()

    @classmethod
    def get_confidence_tier(cls, field_name: str, score: float | None) -> str:
        if score is None or score <= 0.0:
            return "LOW"
        field_cfg = cls.get_field_config(field_name)
        tier_t = field_cfg.tier_thresholds
        if score >= tier_t.high_min:
            return "HIGH"
        elif score >= tier_t.medium_min:
            return "MEDIUM"
        else:
            return "LOW"

    # ------------------------------------------------------------------
    # Scoring rules (externalized hardcoded business rules)
    # ------------------------------------------------------------------

    @classmethod
    def get_scoring(cls, tenant_id: str | None = None) -> ScoringRules:
        return cls.get_config(tenant_id).scoring

    @classmethod
    def get_match_rules(cls, tenant_id: str | None = None) -> MatchScoringRules:
        return cls.get_scoring(tenant_id).match

    @classmethod
    def get_prefilter_rules(cls, tenant_id: str | None = None) -> PrefilterRules:
        return cls.get_scoring(tenant_id).prefilter

    @classmethod
    def get_taxonomy_rules(cls, tenant_id: str | None = None) -> TaxonomyRules:
        return cls.get_scoring(tenant_id).taxonomy

    @classmethod
    def get_resume_quality_rules(cls, tenant_id: str | None = None) -> ResumeQualityRules:
        return cls.get_scoring(tenant_id).resume_quality

    @classmethod
    def get_domain_embedding_rules(cls, tenant_id: str | None = None) -> DomainEmbeddingRules:
        return cls.get_scoring(tenant_id).domain_embedding

    @classmethod
    def _get_cache(cls, tenant_id: str | None = None) -> MappingProxyType:
        with cls._lock:
            tenant_key = tenant_id or 'GLOBAL'
            if tenant_key not in cls._caches or cls._caches[tenant_key].get('config') is not cls._active_configs.get(tenant_key):
                cls.load_config(tenant_id=tenant_id)
            return cls._caches[tenant_key]

    @classmethod
    def get_term_matching_assets(cls, tenant_id: str | None = None) -> MappingProxyType:
        return cls._get_cache(tenant_id)["term_matching"]

    @classmethod
    def get_cross_domain_guard_assets(cls, tenant_id: str | None = None) -> MappingProxyType:
        return cls._get_cache(tenant_id)["cross_domain_guard"]

    @classmethod
    def get_compiled_section_patterns(cls, tenant_id: str | None = None) -> MappingProxyType:
        return cls._get_cache(tenant_id)["compiled"]["section_patterns"]

    @classmethod
    def get_compiled_heading_normalizations(
        cls, tenant_id: str | None = None
    ) -> tuple[tuple[Pattern[str], str], ...]:
        return cls._get_cache(tenant_id)["compiled"]["heading_normalization"]

    @classmethod
    def get_recommendations(cls, tenant_id: str | None = None) -> RecommendationTexts:
        return cls._get_cache(tenant_id)["recommendations"]

    @classmethod
    def get_scoring_parameters(cls, tenant_id: str | None = None) -> ScoringParameters:
        return cls._get_cache(tenant_id)["scoring_parameters"]

    @classmethod
    def get_compiled_cross_domain_guard(cls, tenant_id: str | None = None) -> MappingProxyType:
        return cls._get_cache(tenant_id)["compiled_cross_domain_guard"]

    @classmethod
    def _run_synthetic_smoke_tests(cls, candidate_config: UnifiedRuleConfig) -> None:
        """Execute in-memory synthetic smoke tests against candidate config before activation."""
        try:
            import json

            from app.core.database import PostgresAppSession
            from app.models.rules import RuleValidationTestCase
            
            with PostgresAppSession() as db:
                tests = db.query(RuleValidationTestCase).filter(RuleValidationTestCase.is_active == True).all()
                if not tests:
                    return
                
                config_dict = candidate_config.model_dump()
                for test in tests:
                    try:
                        expected = json.loads(test.expected_result_json)
                        
                        # Dynamically map test.target_component to specific evaluations
                        # e.g., if target_component == "fields.job_title", check candidate_config.fields["job_title"]
                        parts = test.target_component.split('.')
                        current = config_dict
                        for p in parts:
                            if isinstance(current, dict) and p in current:
                                current = current[p]
                            else:
                                current = None
                                break
                        
                        if current is not None and isinstance(current, dict):
                            # Compare expected subset against current configuration
                            for k, v in expected.items():
                                if current.get(k) != v:
                                    raise ValueError(f"Mismatch on '{k}': expected {v}, got {current.get(k)}")
                        elif current is None and expected:
                            raise ValueError(f"Target component '{test.target_component}' not found in configuration")
                    except Exception as test_e:
                        raise ValueError(f"Smoke test '{test.test_name}' failed: {test_e}")
                        
        except ValueError as ve:
            logger.error(f"[RULE_CONFIG] Validation test failure: {ve}")
            raise ve
        except Exception as e:
            logger.warning(f"[RULE_CONFIG] Failed to execute DB smoke tests (DB error): {e}")

    @classmethod
    def compute_policy_digest(cls, config: UnifiedRuleConfig) -> str:
        """Compute deterministic SHA-256 digest representing all active rule configurations."""
        payload = config.model_dump_json()
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def get_policy_digest(cls, tenant_id: str | None = None) -> str:
        """Return the active policy digest for the given tenant."""
        config = cls.get_config(tenant_id=tenant_id)
        return cls.compute_policy_digest(config)


# Sub-Policies for Workstream 4.1 Enterprise Policy Registry
class ExtractionPolicy(BaseModel):
    section_patterns: dict[str, str] = Field(default_factory=dict)
    core_sections: list[str] = Field(default_factory=list)
    heading_denylist: list[str] = Field(default_factory=list)
    heading_compact_denylist: list[str] = Field(default_factory=list)
    heading_substring_denylist: list[str] = Field(default_factory=list)
    location_acceptance_min_confidence: float = Field(default=0.70, ge=0.0, le=1.0)
    default_skill_source_confidence: float = Field(default=0.45, ge=0.0, le=1.0)
    inferred_skill_source_confidence: float = Field(default=0.35, ge=0.0, le=1.0)
    domain_keyword_min_matches: int = Field(default=2, ge=1)
    inferred_role_limit: int = Field(default=4, ge=1)
    garbage_skill_terms: list[str] = Field(
        default_factory=lambda: [
            "-", ".", "yes", "no", "n/a", "na", "nil", "none", "test", "1", "0",
            "ok", "good", "e.g", "e.g.", "i.e", "i.e.", "job overview",
            "key responsibilities", "responsibilities", "requirements",
        ]
    )


class ExperiencePolicy(BaseModel):
    date_parse_tolerance_days: int = Field(default=30, ge=0)
    allow_overlapping_intervals: bool = True
    unknown_date_handling: str = Field(default="UNKNOWN", description="Keep as UNKNOWN, zero addition")
    current_role_recency_days: int = Field(default=365, ge=0)
    gap_threshold_days: int = Field(default=60, ge=1)
    hr_review_gap_months: float = Field(default=3.0, ge=0.0)
    extended_gap_indicator_months: float = Field(default=6.0, ge=0.0)
    minimum_analysis_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    default_analysis_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    placeholder_companies: list[str] = Field(
        default_factory=lambda: ["organization", "company", "n/a", "none", "null", "position", "job title", ""]
    )
    placeholder_titles: list[str] = Field(
        default_factory=lambda: ["position", "job title", "n/a", "none", "null", "organization", "company", ""]
    )
    deputation_keywords: list[str] = Field(default_factory=lambda: ["deputation", "deputed", "secondment"])
    promotion_transfer_keywords: list[str] = Field(
        default_factory=lambda: ["promotion", "promoted", "transfer", "transferred", "rotation"]
    )
    internal_assignment_keywords: list[str] = Field(
        default_factory=lambda: ["sub-role", "internal assignment", "project posting", "project assignment"]
    )
    job_title_keywords: list[str] = Field(
        default_factory=lambda: [
            "sr. executive", "senior executive", "junior executive", "jr. executive", "executive",
            "manager", "developer", "engineer", "analyst", "consultant", "inspector", "director",
            "lead", "officer", "specialist", "qa operations", "field operations", "position",
        ]
    )
    seniority_experience_thresholds: dict[str, float] = Field(
        default_factory=lambda: {"JUNIOR": 1.0, "MID": 3.0, "SENIOR": 5.0, "LEAD": 8.0}
    )


class TaxonomyPolicy(BaseModel):
    semantic_match_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    main_department_match_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    hierarchy_ambiguity_gap: float = Field(default=0.05, ge=0.0, le=1.0)
    family_compatibility_min_score: float = Field(default=0.40, ge=0.0, le=1.0)
    relation_scores: dict[str, float] = Field(
        default_factory=lambda: {
            "EXACT": 1.0,
            "ALLOWED": 0.85,
            "RELATED": 0.50,
            "DISALLOWED": 0.0,
            "UNKNOWN": 0.0,
        }
    )
    canonical_domains: list[str] = Field(default_factory=list)
    canonical_families: list[str] = Field(default_factory=list)


class CertificationEquivalence(BaseModel):
    required_id: str
    accepted_id: str
    relation_type: str = "EQUIVALENT"
    active: bool = True
    tenant_id: str = "GLOBAL"


class EducationEquivalence(BaseModel):
    required_degree_id: str
    accepted_degree_id: str
    relation_type: str = "EXACT"
    active: bool = True
    tenant_id: str = "GLOBAL"


class SeniorityPolicy(BaseModel):
    job_family: str
    level: str
    min_years: float | None = None
    typical_years: float | None = None
    title_signals: list[str] = Field(default_factory=list)
    responsibility_signals: list[str] = Field(default_factory=list)
    tenant_id: str = "GLOBAL"
    version: str = "1.0.0"


class TaxonomyResolutionPolicy(BaseModel):
    embedding_model_version: str = "nomic-embed-text-v1"
    taxonomy_version: str = "v2026.1"
    candidate_accept_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    vacancy_accept_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    ambiguity_margin: float = Field(default=0.10, ge=0.0, le=1.0)
    hard_prune_min_confidence: float = Field(default=0.40, ge=0.0, le=1.0)
    fallback_mode: str = "NO_CONFIDENT_MATCH"


class QualificationPolicy(BaseModel):
    degree_level_hierarchy: dict[str, int] = Field(
        default_factory=lambda: {
            "HIGH_SCHOOL": 1,
            "BACHELOR": 2,
            "MASTER": 3,
            "DOCTORATE": 4,
        }
    )
    degree_aliases: dict[str, str] = Field(
        default_factory=lambda: {
            "ph.d": "DOCTORATE", "phd": "DOCTORATE", "doctorate": "DOCTORATE",
            "m.tech": "MASTERS", "mtech": "MASTERS", "m.s": "MASTERS", "ms": "MASTERS",
            "m.sc": "MASTERS", "msc": "MASTERS", "master": "MASTERS", "masters": "MASTERS",
            "mba": "MASTERS", "m.e": "MASTERS", "me": "MASTERS",
            "b.tech": "BACHELORS", "btech": "BACHELORS", "b.e": "BACHELORS",
            "be": "BACHELORS", "b.s": "BACHELORS", "bs": "BACHELORS",
            "b.sc": "BACHELORS", "bsc": "BACHELORS", "bachelor": "BACHELORS",
            "bachelors": "BACHELORS", "b.a": "BACHELORS", "ba": "BACHELORS",
            "b.com": "BACHELORS", "bcom": "BACHELORS", "diploma": "DIPLOMA",
            "high school": "HIGH_SCHOOL", "secondary": "HIGH_SCHOOL",
        }
    )
    discipline_keywords: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "COMPUTER_SCIENCE": ["computer science", "cs", "computer engineering", "software engineering", "computing"],
            "INFORMATION_TECHNOLOGY": ["information technology", "it", "information systems", "software systems"],
            "FINANCE": ["finance", "accounting", "economics", "financial", "valuation"],
            "BUSINESS": ["business", "management", "administration", "mba"],
            "HUMANITIES": ["history", "arts", "literature", "english", "philosophy", "sociology"],
            "SCIENCE": ["physics", "chemistry", "biology", "mathematics", "stats", "statistics"],
            "ENGINEERING": ["engineering", "engg"],
        }
    )
    discipline_equivalences: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "COMPUTER_SCIENCE": ["COMPUTER_SCIENCE", "INFORMATION_TECHNOLOGY", "ENGINEERING"],
            "INFORMATION_TECHNOLOGY": ["INFORMATION_TECHNOLOGY", "COMPUTER_SCIENCE", "ENGINEERING"],
            "ENGINEERING": ["ENGINEERING", "COMPUTER_SCIENCE", "INFORMATION_TECHNOLOGY"],
            "FINANCE": ["FINANCE", "BUSINESS"],
            "BUSINESS": ["BUSINESS", "FINANCE"],
        }
    )
    certification_aliases: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "AWS Certified Solutions Architect - Professional": [
                "aws certified solutions architect professional",
                "aws solutions architect professional",
                "aws professional solutions architect",
                "aws architect pro",
            ],
            "AWS Certified Solutions Architect - Associate": [
                "aws certified solutions architect associate",
                "aws solutions architect associate",
                "aws architect associate",
                "aws csa associate",
            ],
            "Project Management Professional (PMP)": [
                "project management professional", "pmp", "pmp certified", "pmi pmp",
            ],
            "Certified Kubernetes Application Developer (CKAD)": [
                "ckad", "certified kubernetes application developer",
            ],
            "Certified Kubernetes Administrator (CKA)": [
                "cka", "certified kubernetes administrator",
            ],
            "Certified Information Systems Security Professional (CISSP)": [
                "cissp", "certified information systems security professional",
            ],
        }
    )
    accepted_degree_equivalences: dict[str, list[str]] = Field(default_factory=dict)
    certification_equivalences: list[CertificationEquivalence] = Field(
        default_factory=lambda: [
            CertificationEquivalence(
                required_id="AWS Certified Solutions Architect - Professional",
                accepted_id="AWS Certified Solutions Architect - Associate",
            ),
            CertificationEquivalence(
                required_id="Project Management Professional (PMP)",
                accepted_id="PRINCE2 Practitioner",
            ),
            CertificationEquivalence(
                required_id="Certified Kubernetes Application Developer (CKAD)",
                accepted_id="Certified Kubernetes Administrator (CKA)",
            ),
            CertificationEquivalence(
                required_id="Certified Information Systems Security Professional (CISSP)",
                accepted_id="CISM",
            ),
        ]
    )
    education_equivalences: list[EducationEquivalence] = Field(default_factory=list)
    exact_match_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    equivalent_match_confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class MatchingPolicy(BaseModel):
    mandatory_failure_penalty: float = Field(default=50.0, ge=0.0, le=100.0)
    max_score_on_failure: float = Field(default=49.9, ge=0.0, le=100.0)
    overqualification_penalty: float = Field(default=10.0, ge=0.0, le=100.0)
    domain_mismatch_multiplier: float = Field(default=0.25, ge=0.0, le=1.0)
    allow_assessability_fallback: bool = True


class ScoringPolicy(BaseModel):
    id: str = "scoring_default"
    version: str = "1.0.0"
    active: bool = True
    tenant_id: str = "GLOBAL"
    source: str = "DATABASE"
    change_reason: str = "Canonical enterprise scoring policy"
    match_high_threshold: float = Field(default=75.0, ge=0.0, le=100.0)
    match_medium_threshold: float = Field(default=50.0, ge=0.0, le=100.0)
    component_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "skills": 0.35,
            "role": 0.20,
            "experience": 0.20,
            "responsibilities": 0.15,
            "education": 0.10,
        }
    )
    mandatory_penalty: float = Field(default=50.0, ge=0.0, le=100.0)
    failure_cap: float = Field(default=49.9, ge=0.0, le=100.0)
    llm_semantic_weight: float = Field(default=0.20, ge=0.0, le=1.0)
    max_llm_boost: float = Field(default=10.0, ge=0.0, le=100.0)
    zero_skills_score_cap: float = Field(default=40.0, ge=0.0, le=100.0)
    rejection_score_epsilon: float = Field(default=0.1, gt=0.0, le=100.0)


class RetrievalPolicy(BaseModel):
    stage_0_prefilter_limit: int = Field(default=60, ge=1)
    stage_1_vector_top_n: int = Field(default=30, ge=1)
    rrf_k_constant: float = Field(default=60.0, gt=0.0)
    llm_top_n: int = Field(default=5, ge=1)
    score_decay_stop_threshold: float = Field(default=0.10, ge=0.0, le=1.0)
    vector_candidate_pool: int = Field(default=200, ge=1)
    rerank_top_n: int = Field(default=50, ge=1)
    search_quality_top_k: int = Field(default=10, ge=1)
    rrf_k: float = Field(default=60.0, gt=0.0)
    cache_capacity: int = Field(default=128, ge=1)
    score_floor: float = Field(default=0.05, ge=0.0, le=1.0)
    rerank_retrieval_weight: float = Field(default=0.50, ge=0.0, le=1.0)
    rerank_qualitative_weight: float = Field(default=0.50, ge=0.0, le=1.0)
    missing_qualitative_score: float = Field(default=0.50, ge=0.0, le=1.0)
    section_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "skills": 0.30,
            "experience": 0.30,
            "profile": 0.20,
            "projects": 0.10,
            "domain": 0.10,
        }
    )
    adaptive_strategy: str = "STAGE_0_BYPASS"

    @model_validator(mode="after")
    def validate_weights(self) -> "RetrievalPolicy":
        rerank_total = self.rerank_retrieval_weight + self.rerank_qualitative_weight
        if abs(rerank_total - 1.0) > 1e-6:
            raise ValueError("Retrieval rerank weights must sum to 1.0.")
        if not self.section_weights or sum(self.section_weights.values()) <= 0.0:
            raise ValueError("Retrieval section weights must have a positive total.")
        if any(weight < 0.0 for weight in self.section_weights.values()):
            raise ValueError("Retrieval section weights must not be negative.")
        return self


class RecommendationPolicy(BaseModel):
    career_transition_eligibility_min_score: float = Field(default=45.0, ge=0.0, le=100.0)
    evidence_minimum_confidence: float = Field(default=0.50, ge=0.0, le=1.0)
    list_display_caps: int = Field(default=10, ge=1)


class SimilarityPolicy(BaseModel):
    expected_vector_dimension: int = Field(default=768, ge=1)
    min_similarity_threshold: float = Field(default=0.30, ge=0.0, le=1.0)
    model_fallback_enabled: bool = True


class PolicySnapshotMetadata(BaseModel):
    policy_snapshot_id: str = Field(..., description="Unique snapshot identity e.g. snap_1.0.0_a1b2c3d4")
    version: str = Field(..., description="Rule config semantic version tag")
    status: Literal["ACTIVE", "DEGRADED", "ARCHIVED"] = Field(default="ACTIVE")
    effective_from: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    effective_to: datetime | None = Field(default=None)
    source: Literal["DATABASE", "EMERGENCY_BUNDLED"] = Field(default="DATABASE")
    owner: str = Field(default="system.admin@cv-analyzer.enterprise")
    change_reason: str = Field(default="Verified enterprise policy release snapshot")
    rollback_pointer: str | None = Field(default=None)


class PolicySnapshot(BaseModel):
    metadata: PolicySnapshotMetadata
    extraction: ExtractionPolicy = Field(default_factory=ExtractionPolicy)
    experience: ExperiencePolicy = Field(default_factory=ExperiencePolicy)
    taxonomy: TaxonomyPolicy = Field(default_factory=TaxonomyPolicy)
    qualification: QualificationPolicy = Field(default_factory=QualificationPolicy)
    matching: MatchingPolicy = Field(default_factory=MatchingPolicy)
    scoring: ScoringPolicy = Field(default_factory=ScoringPolicy)
    retrieval: RetrievalPolicy = Field(default_factory=RetrievalPolicy)
    recommendation: RecommendationPolicy = Field(default_factory=RecommendationPolicy)
    similarity: SimilarityPolicy = Field(default_factory=SimilarityPolicy)
    version_digest: str = Field(..., description="SHA-256 fingerprint digest")

    model_config = {"frozen": True}  # Immutable snapshot


class PolicyRegistry:
    """
    Unified Policy & Decision Registry.
    Single-source accessor for versioned scoring parameters, component weights,
    taxonomy classification rules, hiring risk policies, and term matching assets.
    Guarantees deterministic decision semantics across all services.
    """

    @classmethod
    def get_policy_digest(cls, tenant_id: str | None = None) -> str:
        """Return deterministic policy version digest."""
        return RuleConfigManager.get_policy_digest(tenant_id=tenant_id)

    @classmethod
    def get_scoring_parameters(cls, tenant_id: str | None = None) -> ScoringParameters:
        return RuleConfigManager.get_scoring_parameters(tenant_id=tenant_id)

    @classmethod
    def get_scoring_rules(cls, tenant_id: str | None = None) -> ScoringRules:
        return RuleConfigManager.get_scoring(tenant_id=tenant_id)

    @classmethod
    def get_match_rules(cls, tenant_id: str | None = None) -> MatchScoringRules:
        return RuleConfigManager.get_match_rules(tenant_id=tenant_id)

    @classmethod
    def get_taxonomy_rules(cls, tenant_id: str | None = None) -> TaxonomyRules:
        return RuleConfigManager.get_taxonomy_rules(tenant_id=tenant_id)

    @classmethod
    def get_hiring_risk_policies(cls, tenant_id: str | None = None) -> dict[str, HiringRiskPolicy]:
        return RuleConfigManager.get_config(tenant_id=tenant_id).hiring_risks.policies

    @classmethod
    def get_term_matching_assets(cls, tenant_id: str | None = None) -> MappingProxyType:
        return RuleConfigManager.get_term_matching_assets(tenant_id=tenant_id)

    @classmethod
    def get_cross_domain_guard_assets(cls, tenant_id: str | None = None) -> MappingProxyType:
        return RuleConfigManager.get_cross_domain_guard_assets(tenant_id=tenant_id)

    @classmethod
    def get_recommendations(cls, tenant_id: str | None = None) -> RecommendationTexts:
        return RuleConfigManager.get_recommendations(tenant_id=tenant_id)

    @classmethod
    def resolve_snapshot(cls, tenant_id: str | None = None) -> PolicySnapshot:
        """Resolves an immutable, versioned PolicySnapshot for candidate analysis."""
        try:
            config = RuleConfigManager.get_config(tenant_id=tenant_id)
            digest = RuleConfigManager.get_policy_digest(tenant_id=tenant_id)
            meta = PolicySnapshotMetadata(
                policy_snapshot_id=f"snap_{config.version}_{digest[:8]}",
                version=config.version,
                status="DEGRADED" if config.degraded_mode else "ACTIVE",
                source="EMERGENCY_BUNDLED" if config.degraded_mode or config.source == "bundled_static" else config.source,
                owner="system.admin@cv-analyzer.enterprise",
                change_reason="Active database configuration snapshot" if not config.degraded_mode else "Degraded fallback configuration snapshot",
            )
            match_rules = config.scoring.match
            scoring_params = match_rules.scoring_parameters
            cross_guard = match_rules.cross_domain_guard
            tax_rules = config.scoring.taxonomy

            return PolicySnapshot(
                metadata=meta,
                extraction=ExtractionPolicy(
                    heading_denylist=match_rules.cv_section_heading_denylist,
                    heading_compact_denylist=match_rules.cv_section_heading_compact_denylist,
                    heading_substring_denylist=match_rules.cv_section_heading_substring_denylist,
                ),
                experience=ExperiencePolicy(),
                taxonomy=TaxonomyPolicy(
                    semantic_match_threshold=tax_rules.semantic_match_threshold,
                    canonical_domains=tax_rules.canonical_domains,
                    canonical_families=tax_rules.canonical_families,
                ),
                qualification=QualificationPolicy(),
                matching=MatchingPolicy(
                    mandatory_failure_penalty=scoring_params.mandatory_failure_penalty,
                    max_score_on_failure=scoring_params.max_score_on_failure,
                    overqualification_penalty=scoring_params.overqualification_penalty,
                    domain_mismatch_multiplier=cross_guard.domain_mismatch_multiplier,
                ),
                scoring=ScoringPolicy(
                    match_high_threshold=scoring_params.match_high_threshold,
                    match_medium_threshold=scoring_params.match_medium_threshold,
                    component_weights=scoring_params.component_weights,
                    mandatory_penalty=scoring_params.mandatory_failure_penalty,
                    failure_cap=scoring_params.max_score_on_failure,
                    llm_semantic_weight=scoring_params.llm_semantic_weight,
                    max_llm_boost=scoring_params.max_llm_boost,
                    zero_skills_score_cap=scoring_params.zero_skills_score_cap,
                ),
                retrieval=RetrievalPolicy(),
                recommendation=RecommendationPolicy(),
                similarity=SimilarityPolicy(),
                version_digest=digest,
            )
        except Exception as exc:
            logger.warning(f"[POLICY_REGISTRY] Database policy hydration failed ({exc}). Resolving emergency bundled policy snapshot.")
            return cls.get_emergency_bundled_snapshot()

    @classmethod
    def get_emergency_bundled_snapshot(cls) -> PolicySnapshot:
        """Returns explicitly versioned emergency bundled snapshot marked DEGRADED."""
        from app.services.system_rule_config_factory import SystemRuleConfigFactory
        config = SystemRuleConfigFactory.build()
        digest = RuleConfigManager.compute_policy_digest(config)
        meta = PolicySnapshotMetadata(
            policy_snapshot_id=f"snap_emergency_{digest[:8]}",
            version="v1.0.0-emergency-bundled",
            status="DEGRADED",
            source="EMERGENCY_BUNDLED",
            owner="emergency.fallback@cv-analyzer.enterprise",
            change_reason="Emergency bundled profile activated due to database policy unavailability",
            rollback_pointer="v1.0.0-previous",
        )
        return PolicySnapshot(
            metadata=meta,
            extraction=ExtractionPolicy(),
            experience=ExperiencePolicy(),
            taxonomy=TaxonomyPolicy(),
            qualification=QualificationPolicy(),
            matching=MatchingPolicy(),
            scoring=ScoringPolicy(),
            retrieval=RetrievalPolicy(),
            recommendation=RecommendationPolicy(),
            similarity=SimilarityPolicy(),
            version_digest=digest,
        )
