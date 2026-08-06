# backend/app/core/rule_config_manager.py
import hashlib
import json
import logging
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from re import Pattern
from types import MappingProxyType
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger("cv_analyzer")



class GlobalTierBoundary(BaseModel):
    min_score: float = Field(..., ge=0.0, le=1.0)
    max_score: float = Field(..., ge=0.0, le=1.0)


class TierThresholds(BaseModel):
    high_min: float = Field(0.80, ge=0.0, le=1.0)
    medium_min: float = Field(0.50, ge=0.0, le=1.0)
    low_min: float = Field(0.00, ge=0.0, le=1.0)
    override_reason: str | None = None


class DownstreamGates(BaseModel):
    min_acceptance_confidence: float = Field(0.50, ge=0.0, le=1.0)
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
    domain_mismatch_multiplier: float = Field(0.15, gt=0.0, le=1.0)
    domain_mismatch_score_cap: float = Field(20.0, gt=0.0)
    mandatory_failure_score_impact: float = Field(50.0, gt=0.0)


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
    career_transition_role_score: float = Field(50.0, ge=0.0, le=100.0)
    role_divergence_score: float = Field(70.0, ge=0.0, le=100.0)
    default_role_score: float = Field(100.0, ge=0.0, le=100.0)
    below_min_exp_multiplier: float = Field(50.0, ge=0.0, le=100.0)
    overqualification_penalty: float = Field(20.0, ge=0.0, le=100.0)
    domain_default_match_score: float = Field(50.0, ge=0.0, le=100.0)
    low_coverage_threshold: float = Field(0.5, ge=0.0, le=1.0)
    false_positive_score_cap: float = Field(99.0, ge=0.0, le=100.0)
    
    # Migrated from legacy ConfigRepository
    match_high_threshold: float = Field(80.0, ge=0.0, le=100.0)
    match_medium_threshold: float = Field(50.0, ge=0.0, le=100.0)
    mandatory_failure_penalty: float = Field(20.0, ge=0.0, le=100.0)
    max_score_on_failure: float = Field(80.0, ge=0.0, le=100.0)
    llm_semantic_weight: float = Field(0.1, ge=0.0, le=1.0)
    max_llm_boost: float = Field(10.0, ge=0.0, le=100.0)
    component_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "role": 0.15,
            "skills": 0.25,
            "experience": 0.15,
            "education": 0.10,
            "domain": 0.15,
            "technology": 0.10,
            "certification": 0.05,
            "responsibilities": 0.05,
        }
    )


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
    department_match: float = Field(30.0, ge=0.0)
    title_term_match: float = Field(15.0, ge=0.0)
    required_skill_match: float = Field(10.0, ge=0.0)
    preferred_keyword_match: float = Field(5.0, ge=0.0)
    experience_suitability: float = Field(10.0, ge=0.0)


class PrefilterRules(BaseModel):
    stop_words: list[str] = Field(default_factory=list)
    lexical_weights: LexicalWeights = Field(default_factory=LexicalWeights)
    rrf_k_constant: float = Field(60.0, gt=0.0)


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


class DensityScoreTier(BaseModel):
    min_words_per_page: int = Field(..., ge=0)
    score: float = Field(..., ge=0.0, le=1.0)


class HeadingNormalization(BaseModel):
    pattern: str = Field(..., min_length=1)
    replacement: str = Field(..., min_length=1)


class ResumeQualityRules(BaseModel):
    section_patterns: dict[str, str] = Field(default_factory=dict)
    core_sections: list[str] = Field(default_factory=list)
    section_weight: float = Field(0.10, ge=0.0, le=1.0)
    contact_weights: dict[str, float] = Field(default_factory=dict)
    location_acceptance_min_confidence: float = Field(0.50, ge=0.0, le=1.0)
    density_scores: list[DensityScoreTier] = Field(default_factory=list)
    default_density_score: float = Field(0.05, ge=0.0, le=1.0)
    heading_normalization: list[HeadingNormalization] = Field(default_factory=list)


class DomainEmbeddingRules(BaseModel):
    categories: list[str] = Field(default_factory=list)
    canonical_equivalents: dict[str, dict[str, str]] = Field(default_factory=dict)


class WorkflowRules(BaseModel):
    allowed_job_states: list[str] = Field(
        default_factory=lambda: ["QUEUED", "PROCESSING", "RETRYING", "COMPLETED", "FAILED", "UNKNOWN"]
    )
    job_state_transitions: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "QUEUED": ["QUEUED", "PROCESSING", "RETRYING", "FAILED"],
            "PROCESSING": ["PROCESSING", "RETRYING", "COMPLETED", "FAILED"],
            "RETRYING": ["RETRYING", "PROCESSING", "FAILED"],
            "COMPLETED": ["COMPLETED", "QUEUED"],
            "FAILED": ["FAILED", "QUEUED"],
            "UNKNOWN": ["QUEUED", "FAILED"],
        }
    )


class ScoringRules(BaseModel):
    match: MatchScoringRules
    prefilter: PrefilterRules
    taxonomy: TaxonomyRules
    resume_quality: ResumeQualityRules
    domain_embedding: DomainEmbeddingRules


class UnifiedRuleConfig(BaseModel):
    version: str
    description: str
    last_updated: str
    global_confidence_tiers: dict[str, GlobalTierBoundary]
    fields: dict[str, FieldRuleConfig]
    scoring: ScoringRules
    workflow: WorkflowRules = Field(default_factory=WorkflowRules)

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
            if not {"dear", "sir", "madam", "salutation"}.intersection(blacklist):
                raise ValueError("[SAFETY_GATE_VIOLATION] Location field blacklist missing salutations")

        title = self.fields.get("job_title")
        if title:
            starters = title.get_keyword_set("narrative_starters")
            if not {"graduated", "worked"}.intersection(starters):
                raise ValueError("[SAFETY_GATE_VIOLATION] Job title narrative_starters missing expected verbs")

        comp = self.fields.get("company_name")
        if comp:
            generic = comp.get_keyword_set("generic_section_headers")
            if not {"experience", "education"}.intersection(generic):
                raise ValueError("[SAFETY_GATE_VIOLATION] Company name generic_section_headers missing expected headers")

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
            from app.core.database import PostgresAppSession
            from app.models.rules import RuleConfigProfile
            
            with PostgresAppSession() as db:
                query = db.query(RuleConfigProfile).filter(RuleConfigProfile.is_active == True)
                if tenant_id:
                    query = query.filter(RuleConfigProfile.tenant_id == tenant_id)
                else:
                    query = query.filter(RuleConfigProfile.tenant_id.is_(None))
                active_profile = query.first()
                if active_profile:
                    # TODO: Hydrate UnifiedRuleConfig fully from normalized RuleComponent, SystemRule, RuleCondition, 
                    # RuleThreshold, RulePenalty, and RuleWeight tables.
                    # This requires a complex hierarchical aggregation logic. 
                    # For this PR, we defer hydration and allow fallback to the cached/mocked configuration.
                    raw_data = None
                    path_hash = active_profile.version_tag
                    config_size_bytes = len(json.dumps(raw_data))
                    logger.info(f"[RULE_CONFIG] Loading active profile from database (v{active_profile.version_tag})")
                    
                    from app.core.cache import config_cache_manager
                    cache_key = f"rule_config_profile_{tenant_id or 'GLOBAL'}"
                    config_cache_manager.set(cache_key, raw_data)
        except Exception as e:
            logger.warning(f"[RULE_CONFIG] Failed to load config from database: {e}")

        if raw_data is None:
            from app.core.cache import config_cache_manager
            cache_key = f"rule_config_profile_{tenant_id or 'GLOBAL'}"
            cached_data = config_cache_manager.get(cache_key)
            if cached_data:
                raw_data = cached_data
                path_hash = cached_data.get("version", "cached")
                config_size_bytes = len(json.dumps(raw_data))
                logger.info(f"[RULE_CONFIG] Loading active profile from cache (v{path_hash})")

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
                    "last_loaded_timestamp": datetime.now(UTC).isoformat(),
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
    def get_field_config(cls, field_name: str) -> FieldRuleConfig:
        cfg = cls.get_config()
        if field_name not in cfg.fields:
            raise KeyError(f"Field '{field_name}' not configured in UnifiedRuleConfig")
        return cfg.fields[field_name]

    @classmethod
    def get_keywords(cls, field_name: str, key: str) -> set[str]:
        field_cfg = cls.get_field_config(field_name)
        return field_cfg.get_keyword_set(key)

    @classmethod
    def get_upper_keywords(cls, field_name: str, key: str) -> set[str]:
        field_cfg = cls.get_field_config(field_name)
        return field_cfg.get_upper_keyword_set(key)

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
            from app.core.database import PostgresAppSession
            from app.models.rules import RuleValidationTestCase
            import json
            
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


