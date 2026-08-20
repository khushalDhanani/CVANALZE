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

        from app.core.rule_config_manager import PolicyRegistry
        snapshot = PolicyRegistry.resolve_snapshot(tenant_id=tenant_id)
        scoring = snapshot.scoring
        matching = snapshot.matching
        return cls(
            profile_code=snapshot.metadata.source,
            profile_version=snapshot.metadata.version,
            perfect_component_score=100.0,
            penalty_per_item=matching.mandatory_failure_penalty,
            max_score_on_failure=matching.max_score_on_failure,
            llm_semantic_weight=scoring.llm_semantic_weight,
            max_llm_boost=scoring.max_llm_boost,
            match_high_threshold=scoring.match_high_threshold,
            match_medium_threshold=scoring.match_medium_threshold,
            zero_skills_score_cap=scoring.zero_skills_score_cap,
            rejection_score_epsilon=scoring.rejection_score_epsilon,
            component_weights=dict(scoring.component_weights),
        )
