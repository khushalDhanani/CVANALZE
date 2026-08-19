from __future__ import annotations

from app.schemas.scoring_config import DEFAULT_COMPONENT_WEIGHTS, ScoringConfig
from app.services.scoring_engine import ScoringEngine


def test_default_component_weights_sum() -> None:
    weights = DEFAULT_COMPONENT_WEIGHTS
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.001
    assert "skills" in weights
    assert "experience" in weights
    assert "role" in weights


def test_scoring_engine_extract_candidate_domain_profile(sample_candidate_cv_text: str) -> None:
    profile = ScoringEngine.extract_candidate_domain_profile(sample_candidate_cv_text)
    assert isinstance(profile, dict)
    assert "professional_domain" in profile or "recommended_department" in profile
