from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.repositories.config import ConfigRepository


@dataclass
class ScoringConfig:
    """
    Strongly-typed scoring configuration loaded once per CV analysis run.
    Eliminates repetitive repository access inside evaluator loops.
    """

    penalty_per_item: float = 15.0
    max_score_on_failure: float = 45.0
    llm_semantic_weight: float = 0.15
    max_llm_boost: float = 15.0
    match_high_threshold: float = 80.0
    match_medium_threshold: float = 50.0
    component_weights: dict[str, float] = field(
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

    @classmethod
    def load(cls, override_config: dict[str, Any] | None = None) -> "ScoringConfig":
        default_weights = {
            "role": 0.15,
            "skills": 0.25,
            "experience": 0.15,
            "education": 0.10,
            "domain": 0.15,
            "technology": 0.10,
            "certification": 0.05,
            "responsibilities": 0.05,
        }
        if override_config:
            raw_w = override_config.get("MATCH_COMPONENT_WEIGHTS")
            weights = raw_w if isinstance(raw_w, dict) and raw_w else default_weights
            return cls(
                penalty_per_item=float(override_config.get("MANDATORY_FAILURE_PENALTY_PER_ITEM", 15.0)),
                max_score_on_failure=float(override_config.get("MAX_SCORE_ON_MANDATORY_FAILURE", 45.0)),
                llm_semantic_weight=float(override_config.get("LLM_SEMANTIC_WEIGHT", 0.15)),
                max_llm_boost=float(override_config.get("MAX_LLM_BOOST", 15.0)),
                match_high_threshold=float(override_config.get("MATCH_HIGH_THRESHOLD", 80.0)),
                match_medium_threshold=float(override_config.get("MATCH_MEDIUM_THRESHOLD", 50.0)),
                component_weights=weights,
            )

        raw_w = ConfigRepository.get_setting("MATCH_COMPONENT_WEIGHTS", default_weights)
        weights = raw_w if isinstance(raw_w, dict) and raw_w else default_weights

        return cls(
            penalty_per_item=float(
                ConfigRepository.get_setting(
                    "MANDATORY_FAILURE_PENALTY_PER_ITEM", settings.MANDATORY_FAILURE_PENALTY_PER_ITEM
                )
            ),
            max_score_on_failure=float(
                ConfigRepository.get_setting(
                    "MAX_SCORE_ON_MANDATORY_FAILURE", settings.MAX_SCORE_ON_MANDATORY_FAILURE
                )
            ),
            llm_semantic_weight=float(
                ConfigRepository.get_setting("LLM_SEMANTIC_WEIGHT", settings.LLM_SEMANTIC_WEIGHT)
            ),
            max_llm_boost=float(
                ConfigRepository.get_setting("MAX_LLM_BOOST", settings.MAX_LLM_BOOST)
            ),
            match_high_threshold=float(
                ConfigRepository.get_setting("MATCH_HIGH_THRESHOLD", settings.MATCH_HIGH_THRESHOLD)
            ),
            match_medium_threshold=float(
                ConfigRepository.get_setting("MATCH_MEDIUM_THRESHOLD", settings.MATCH_MEDIUM_THRESHOLD)
            ),
            component_weights=weights,
        )
