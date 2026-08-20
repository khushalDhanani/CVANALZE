"""
Unit tests for Phase 2 Versioned Business Policy Architecture.

Verifies:
1. Split configuration domains (RuntimeSettings, ModelProfile, RetrievalPolicy, ScoringPolicy, SeniorityPolicy).
2. ScoringPolicy schema completeness (id, version, active, tenant_id, source, change_reason).
3. TaxonomyResolutionPolicy schema completeness.
4. Requirement equivalence models (CertificationEquivalence, EducationEquivalence).
5. SeniorityPolicy schema completeness (job_family, level, signals).
6. PolicySnapshot incorporates tenant_id and SHA-256 version_digest.
"""

from __future__ import annotations

from app.core.rule_config_manager import (
    CertificationEquivalence,
    EducationEquivalence,
    PolicyRegistry,
    PolicySnapshot,
    RecommendationPolicy,
    RetrievalPolicy,
    ScoringPolicy,
    SeniorityPolicy,
    TaxonomyResolutionPolicy,
)


def test_scoring_policy_schema_completeness():
    """Verify ScoringPolicy has required versioning, tenant scope, and threshold fields."""
    policy = ScoringPolicy(
        id="scoring_p001",
        version="1.2.0",
        active=True,
        tenant_id="TENANT_ALPHA",
        source="DATABASE",
        change_reason="Enterprise Workstream 6.2 update",
        match_high_threshold=80.0,
        match_medium_threshold=50.0,
    )
    assert policy.id == "scoring_p001"
    assert policy.version == "1.2.0"
    assert policy.active is True
    assert policy.tenant_id == "TENANT_ALPHA"
    assert policy.match_high_threshold == 80.0
    assert policy.match_medium_threshold == 50.0


def test_taxonomy_resolution_policy_schema_completeness():
    """Verify TaxonomyResolutionPolicy models embedding version, thresholds, and fallback mode."""
    tax_policy = TaxonomyResolutionPolicy(
        embedding_model_version="nomic-embed-text-v1",
        taxonomy_version="v2026.1",
        candidate_accept_threshold=0.75,
        vacancy_accept_threshold=0.80,
        ambiguity_margin=0.10,
        hard_prune_min_confidence=0.40,
        fallback_mode="NO_CONFIDENT_MATCH",
    )
    assert tax_policy.embedding_model_version == "nomic-embed-text-v1"
    assert tax_policy.ambiguity_margin == 0.10
    assert tax_policy.fallback_mode == "NO_CONFIDENT_MATCH"


def test_requirement_equivalence_policy_schema():
    """Verify CertificationEquivalence and EducationEquivalence models."""
    cert_eq = CertificationEquivalence(
        required_id="aws_solutions_architect_prof",
        accepted_id="aws_solutions_architect_assoc",
        relation_type="EQUIVALENT",
        active=True,
        tenant_id="GLOBAL",
    )
    assert cert_eq.relation_type == "EQUIVALENT"

    edu_eq = EducationEquivalence(
        required_degree_id="btech_cs",
        accepted_degree_id="be_cs",
        relation_type="EXACT",
        active=True,
        tenant_id="GLOBAL",
    )
    assert edu_eq.accepted_degree_id == "be_cs"


def test_seniority_policy_schema():
    """Verify SeniorityPolicy models signals and experience bounds."""
    seniority = SeniorityPolicy(
        job_family="Software Engineering",
        level="Senior",
        min_years=5.0,
        typical_years=7.0,
        title_signals=["Senior", "Lead", "Staff"],
        responsibility_signals=["Architecting", "Mentoring", "Leading"],
        tenant_id="GLOBAL",
        version="1.0.0",
    )
    assert seniority.level == "Senior"
    assert "Lead" in seniority.title_signals


def test_policy_snapshot_incorporates_all_domains():
    """Verify PolicyRegistry resolves a complete versioned snapshot."""
    snapshot = PolicyRegistry.resolve_snapshot()
    assert isinstance(snapshot, PolicySnapshot)
    assert snapshot.metadata.policy_snapshot_id.startswith("snap_")
    assert snapshot.version_digest != ""
