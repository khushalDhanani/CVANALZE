from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Canonical single source of truth for base scoring configuration defaults
DEFAULT_COMPONENT_WEIGHTS: dict[str, float] = {
    "role": 0.10,
    "skills": 0.20,
    "experience": 0.25,
    "education": 0.05,
    "domain": 0.15,
    "technology": 0.10,
    "certification": 0.05,
    "responsibilities": 0.10,
}

DEFAULT_PERFECT_COMPONENT_SCORE: float = 100.0
DEFAULT_PENALTY_PER_ITEM: float = 15.0
DEFAULT_MAX_SCORE_ON_FAILURE: float = 45.0
DEFAULT_LLM_SEMANTIC_WEIGHT: float = 0.15
DEFAULT_MAX_LLM_BOOST: float = 15.0
DEFAULT_MATCH_HIGH_THRESHOLD: float = 80.0
DEFAULT_MATCH_MEDIUM_THRESHOLD: float = 50.0
DEFAULT_ZERO_SKILLS_SCORE_CAP: float = 40.0
DEFAULT_REJECTION_SCORE_EPSILON: float = 0.1


@dataclass
class ScoringConfig:
    """
    Strongly-typed scoring configuration loaded once per CV analysis run.
    Eliminates repetitive repository access inside evaluator loops.
    """
    profile_code: str = "DEFAULT"
    profile_version: str = "v1"

    perfect_component_score: float = DEFAULT_PERFECT_COMPONENT_SCORE
    penalty_per_item: float = DEFAULT_PENALTY_PER_ITEM
    max_score_on_failure: float = DEFAULT_MAX_SCORE_ON_FAILURE
    llm_semantic_weight: float = DEFAULT_LLM_SEMANTIC_WEIGHT
    max_llm_boost: float = DEFAULT_MAX_LLM_BOOST
    match_high_threshold: float = DEFAULT_MATCH_HIGH_THRESHOLD
    match_medium_threshold: float = DEFAULT_MATCH_MEDIUM_THRESHOLD
    zero_skills_score_cap: float = DEFAULT_ZERO_SKILLS_SCORE_CAP
    rejection_score_epsilon: float = DEFAULT_REJECTION_SCORE_EPSILON
    component_weights: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_COMPONENT_WEIGHTS)
    )

    @property
    def is_fallback(self) -> bool:
        """Return True if this configuration is operating in fallback/degraded mode."""
        return self.profile_code == "FALLBACK"

    def calculate_rejection_cap(self, threshold: float | None = None, precision: int | None = None) -> float:
        """
        Return the upper score cap for rejected matches to ensure they remain strictly below
        the borderline/potential match threshold and avoid numerical ties or contradictions.
        Dynamically adapts rounding precision if a finer epsilon/threshold granularity is configured.
        """
        base = threshold if threshold is not None else self.match_medium_threshold
        eps = self.rejection_score_epsilon
        if precision is not None:
            return round(max(0.0, base - eps), precision)
        eps_str = f"{eps:.10f}".rstrip("0").rstrip(".")
        decimals = max(1, len(eps_str.split(".")[1])) if "." in eps_str else 1
        return round(max(0.0, base - eps), decimals)

    @classmethod
    def load(cls, override_config: dict[str, Any] | None = None, tenant_id: str | None = None) -> "ScoringConfig":
        if override_config:
            raw_w = override_config.get("MATCH_COMPONENT_WEIGHTS")
            weights = raw_w if isinstance(raw_w, dict) and raw_w else dict(DEFAULT_COMPONENT_WEIGHTS)
            return cls(
                profile_code="OVERRIDE",
                profile_version="custom",
                perfect_component_score=float(override_config.get("PERFECT_COMPONENT_SCORE", DEFAULT_PERFECT_COMPONENT_SCORE)),
                penalty_per_item=float(override_config.get("MANDATORY_FAILURE_PENALTY_PER_ITEM", DEFAULT_PENALTY_PER_ITEM)),
                max_score_on_failure=float(override_config.get("MAX_SCORE_ON_MANDATORY_FAILURE", DEFAULT_MAX_SCORE_ON_FAILURE)),
                llm_semantic_weight=float(override_config.get("LLM_SEMANTIC_WEIGHT", DEFAULT_LLM_SEMANTIC_WEIGHT)),
                max_llm_boost=float(override_config.get("MAX_LLM_BOOST", DEFAULT_MAX_LLM_BOOST)),
                match_high_threshold=float(override_config.get("MATCH_HIGH_THRESHOLD", DEFAULT_MATCH_HIGH_THRESHOLD)),
                match_medium_threshold=float(override_config.get("MATCH_MEDIUM_THRESHOLD", DEFAULT_MATCH_MEDIUM_THRESHOLD)),
                zero_skills_score_cap=float(override_config.get("ZERO_SKILLS_SCORE_CAP", DEFAULT_ZERO_SKILLS_SCORE_CAP)),
                rejection_score_epsilon=float(override_config.get("REJECTION_SCORE_EPSILON", DEFAULT_REJECTION_SCORE_EPSILON)),
                component_weights=weights,
            )

        try:
            from app.core.rule_config_manager import RuleConfigManager
            from app.services.dynamic_scoring_prefilter_service import DynamicScoringAndPrefilterService

            # Fetch from DB-backed ScoringProfileMaster
            tenant_key = tenant_id or "DEFAULT"
            profile = DynamicScoringAndPrefilterService.get_tenant_scoring_profile(tenant_key)

            # Fetch from rule_config.json DB fallbacks
            params = RuleConfigManager.get_scoring_parameters(tenant_id=tenant_id)

            penalties = profile.get("penalties", {})
            thresholds = profile.get("thresholds", {})
            comp_weights = profile.get("component_weights", {})

            final_weights = comp_weights if comp_weights else params.component_weights

            return cls(
                profile_code=profile.get("profile_code", "DEFAULT"),
                profile_version=profile.get("profile_version", "v1"),
                penalty_per_item=float(penalties.get("mandatory_failure_penalty", params.mandatory_failure_penalty)),
                max_score_on_failure=float(penalties.get("max_score_on_failure", params.max_score_on_failure)),
                llm_semantic_weight=float(thresholds.get("llm_semantic_weight", params.llm_semantic_weight)),
                max_llm_boost=float(thresholds.get("max_llm_boost", params.max_llm_boost)),
                match_high_threshold=float(thresholds.get("match_high_threshold", params.match_high_threshold)),
                match_medium_threshold=float(thresholds.get("match_medium_threshold", params.match_medium_threshold)),
                zero_skills_score_cap=float(penalties.get("zero_skills_score_cap", getattr(params, "zero_skills_score_cap", DEFAULT_ZERO_SKILLS_SCORE_CAP))),
                component_weights=final_weights,
            )

        except Exception as e:
            # Check if RuleConfigManager already has an active in-memory configuration for this tenant or globally
            try:
                from app.core.rule_config_manager import RuleConfigManager
                if RuleConfigManager.is_config_loaded(tenant_id) or RuleConfigManager.is_config_loaded(None):
                    active_params = RuleConfigManager.get_scoring_parameters(tenant_id=tenant_id)
                    return cls(
                        profile_code="DEFAULT",
                        profile_version="v1",
                        penalty_per_item=float(active_params.mandatory_failure_penalty),
                        max_score_on_failure=float(active_params.max_score_on_failure),
                        llm_semantic_weight=float(active_params.llm_semantic_weight),
                        max_llm_boost=float(active_params.max_llm_boost),
                        match_high_threshold=float(active_params.match_high_threshold),
                        match_medium_threshold=float(active_params.match_medium_threshold),
                        zero_skills_score_cap=float(getattr(active_params, "zero_skills_score_cap", DEFAULT_ZERO_SKILLS_SCORE_CAP)),
                        component_weights=active_params.component_weights,
                    )
            except Exception:
                pass

            import logging
            logger = logging.getLogger("cv_analyzer")
            logger.warning(f"Failed to load dynamic scoring config: {e}. Using defaults.")
            # Fallback to static defaults only if both DB and in-memory caches are unavailable
            return cls(
                profile_code="FALLBACK",
                profile_version="v0",
            )

