from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any



@dataclass
class ScoringConfig:
    """
    Strongly-typed scoring configuration loaded once per CV analysis run.
    Eliminates repetitive repository access inside evaluator loops.
    """
    profile_code: str = "DEFAULT"
    profile_version: str = "v1"

    perfect_component_score: float = 100.0
    penalty_per_item: float = 15.0
    max_score_on_failure: float = 45.0
    llm_semantic_weight: float = 0.15
    max_llm_boost: float = 15.0
    match_high_threshold: float = 80.0
    match_medium_threshold: float = 50.0
    component_weights: dict[str, float] = field(
        default_factory=lambda: {
            "role": 0.10,
            "skills": 0.20,
            "experience": 0.25,
            "education": 0.05,
            "domain": 0.15,
            "technology": 0.10,
            "certification": 0.05,
            "responsibilities": 0.10,
        }
    )

    @classmethod
    def load(cls, override_config: dict[str, Any] | None = None, tenant_id: str | None = None) -> "ScoringConfig":
        default_weights = {
            "role": 0.10,
            "skills": 0.20,
            "experience": 0.25,
            "education": 0.05,
            "domain": 0.15,
            "technology": 0.10,
            "certification": 0.05,
            "responsibilities": 0.10,
        }
        if override_config:
            raw_w = override_config.get("MATCH_COMPONENT_WEIGHTS")
            weights = raw_w if isinstance(raw_w, dict) and raw_w else default_weights
            return cls(
                profile_code="OVERRIDE",
                profile_version="custom",
                penalty_per_item=float(override_config.get("MANDATORY_FAILURE_PENALTY_PER_ITEM", 15.0)),
                max_score_on_failure=float(override_config.get("MAX_SCORE_ON_MANDATORY_FAILURE", 45.0)),
                llm_semantic_weight=float(override_config.get("LLM_SEMANTIC_WEIGHT", 0.15)),
                max_llm_boost=float(override_config.get("MAX_LLM_BOOST", 15.0)),
                match_high_threshold=float(override_config.get("MATCH_HIGH_THRESHOLD", 80.0)),
                match_medium_threshold=float(override_config.get("MATCH_MEDIUM_THRESHOLD", 50.0)),
                component_weights=weights,
            )

        try:
            from app.services.dynamic_scoring_prefilter_service import DynamicScoringAndPrefilterService
            from app.core.rule_config_manager import RuleConfigManager
            
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
                component_weights=final_weights,
            )

        except Exception as e:
            import logging
            logger = logging.getLogger("cv_analyzer")
            logger.warning(f"Failed to load dynamic scoring config: {e}. Using defaults.")
            # Fallback to defaults if the manager is not initialized
            return cls(
                profile_code="FALLBACK",
                profile_version="v0",
            )
