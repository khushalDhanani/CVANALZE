from __future__ import annotations
from pydantic import BaseModel, Field


class MatchEngineConfigUpdate(BaseModel):
    MATCH_HIGH_THRESHOLD: float | None = Field(None, description="Score threshold for HIGH match")
    MATCH_MEDIUM_THRESHOLD: float | None = Field(None, description="Score threshold for MEDIUM match")
    MANDATORY_FAILURE_PENALTY_PER_ITEM: float | None = Field(None, description="Score penalty for missing a mandatory requirement")
    MAX_SCORE_ON_MANDATORY_FAILURE: float | None = Field(
        None,
        description="Maximum score possible if a mandatory requirement fails",
    )
    LLM_SEMANTIC_WEIGHT: float | None = Field(None, description="Weight of LLM semantic match score")
    MAX_LLM_BOOST: float | None = Field(None, description="Maximum points LLM semantic match can add")
    LLM_SKIP_MARGIN_THRESHOLD: float | None = Field(None, description="Margin threshold for LLM skip")
    LLM_SKIP_COVERAGE_THRESHOLD: float | None = Field(None, description="Coverage threshold for LLM skip")
    MATCH_COMPONENT_WEIGHTS: dict[str, float] | None = Field(None, description="Weights for different score components")


class MatchEngineConfigResponse(MatchEngineConfigUpdate):
    pass
