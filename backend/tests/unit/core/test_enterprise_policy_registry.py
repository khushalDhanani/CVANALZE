from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.core.rule_config_manager import (
    ExtractionPolicy,
    ExperiencePolicy,
    MatchingPolicy,
    PolicyRegistry,
    PolicySnapshot,
    QualificationPolicy,
    RecommendationPolicy,
    RetrievalPolicy,
    ScoringPolicy,
    SimilarityPolicy,
    TaxonomyPolicy,
)


def test_policy_registry_snapshot_resolution() -> None:
    """Workstream 4.1: PolicyRegistry resolves an immutable PolicySnapshot with all 9 sub-policies."""
    snapshot = PolicyRegistry.resolve_snapshot()

    assert isinstance(snapshot, PolicySnapshot)
    assert isinstance(snapshot.extraction, ExtractionPolicy)
    assert isinstance(snapshot.experience, ExperiencePolicy)
    assert isinstance(snapshot.taxonomy, TaxonomyPolicy)
    assert isinstance(snapshot.qualification, QualificationPolicy)
    assert isinstance(snapshot.matching, MatchingPolicy)
    assert isinstance(snapshot.scoring, ScoringPolicy)
    assert isinstance(snapshot.retrieval, RetrievalPolicy)
    assert isinstance(snapshot.recommendation, RecommendationPolicy)
    assert isinstance(snapshot.similarity, SimilarityPolicy)
    assert len(snapshot.version_digest) == 16


def test_policy_snapshot_metadata_contracts() -> None:
    """Workstream 4.1: PolicySnapshot incorporates complete provenance metadata."""
    snapshot = PolicyRegistry.resolve_snapshot()
    meta = snapshot.metadata

    assert meta.policy_snapshot_id.startswith("snap_")
    assert meta.version != ""
    assert meta.status in ("ACTIVE", "DEGRADED", "ARCHIVED")
    assert meta.source in ("DATABASE", "EMERGENCY_BUNDLED")
    assert meta.owner != ""
    assert meta.change_reason != ""


def test_policy_snapshot_immutability() -> None:
    """Workstream 4.1: PolicySnapshot is frozen and cannot be mutated at runtime."""
    snapshot = PolicyRegistry.resolve_snapshot()

    with pytest.raises(ValidationError):
        snapshot.version_digest = "mutated_hash_123"  # type: ignore[misc]


def test_emergency_bundled_profile_fallback() -> None:
    """Workstream 4.1: Resolves explicitly versioned emergency snapshot tagged DEGRADED when database policy fails."""
    with patch("app.core.rule_config_manager.RuleConfigManager.get_config", side_effect=RuntimeError("DB Connection Lost")):
        emergency_snapshot = PolicyRegistry.resolve_snapshot()

        assert emergency_snapshot.metadata.source == "EMERGENCY_BUNDLED"
        assert emergency_snapshot.metadata.status == "DEGRADED"
        assert emergency_snapshot.metadata.version == "v1.0.0-emergency-bundled"
        assert emergency_snapshot.metadata.rollback_pointer is not None
        assert isinstance(emergency_snapshot.scoring, ScoringPolicy)


def test_sub_policies_own_domain_parameters() -> None:
    """Workstream 4.1: Sub-policies own specific enterprise domain parameters."""
    snapshot = PolicyRegistry.resolve_snapshot()

    # MatchingPolicy mandatory failure & overqualification parameters
    assert snapshot.matching.mandatory_failure_penalty >= 0.0
    assert snapshot.matching.max_score_on_failure <= 100.0
    assert snapshot.matching.overqualification_penalty >= 0.0

    # ScoringPolicy component weights & thresholds
    assert snapshot.scoring.match_high_threshold >= 50.0
    assert snapshot.scoring.match_medium_threshold >= 0.0
    assert "skills" in snapshot.scoring.component_weights

    # RetrievalPolicy RRF & limits
    assert snapshot.retrieval.rrf_k_constant == 60.0
    assert snapshot.retrieval.stage_0_prefilter_limit == 60

    # QualificationPolicy hierarchy
    assert snapshot.qualification.degree_level_hierarchy["BACHELOR"] == 2
    assert snapshot.qualification.degree_level_hierarchy["DOCTORATE"] == 4
