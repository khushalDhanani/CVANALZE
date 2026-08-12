# backend/tests/test_dynamic_scoring_prefilter_service.py
from app.services.dynamic_scoring_prefilter_service import (
    DynamicScoringAndPrefilterService,
)


def test_get_stop_words():
    stop_words = DynamicScoringAndPrefilterService.get_stop_words()
    assert isinstance(stop_words, set)
    assert len(stop_words) > 0
    assert "and" in stop_words or "team" in stop_words


def test_get_prefilter_rules():
    rules = DynamicScoringAndPrefilterService.get_prefilter_rules()
    assert rules is not None
    assert len(rules.stop_words) > 0
    assert rules.lexical_weights is not None
    assert rules.lexical_weights.department_match > 0


def test_get_tenant_scoring_profile():
    profile = DynamicScoringAndPrefilterService.get_tenant_scoring_profile("DEFAULT")
    assert profile is not None
    assert "lexical_weights" in profile
    assert "penalties" in profile
    assert "thresholds" in profile
