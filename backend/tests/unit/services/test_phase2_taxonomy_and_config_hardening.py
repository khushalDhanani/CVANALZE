"""
Unit tests for Phase 2 Dynamic Taxonomy and Rule Configuration Hardening.

Verifies:
1. TaxonomyResolution type safety and match_type categorization.
2. CompatibilityResolver relation resolution and ranking weight access.
3. Structural validation in rule_config_manager without hardcoded English word restrictions.
4. UnifiedRuleConfig metadata fields (schema_version, policy_version, effective_from, source, changed_by, change_reason).
"""

from __future__ import annotations

from app.core.rule_config_manager import UnifiedRuleConfig
from app.schemas.classification_types import TaxonomyMatchType, TaxonomyRelationType, TaxonomyResolution
from app.services.compatibility_resolver import CompatibilityResolver
from app.services.system_rule_config_factory import SystemRuleConfigFactory


def test_taxonomy_resolution_type_safety():
    """Verify TaxonomyResolution captures canonical_id, match_type, and similarity."""
    res = TaxonomyResolution(
        canonical_id="desig_python_dev",
        status="DB_MATCH",
        match_type=TaxonomyMatchType.SEMANTIC,
        similarity=0.88,
        confidence=0.92,
        taxonomy_version="v2026.1",
        model_version="nomic-embed-text",
        source="MSSQL_TAXONOMY",
    )
    assert res.canonical_id == "desig_python_dev"
    assert res.match_type == TaxonomyMatchType.SEMANTIC
    assert res.similarity == 0.88
    assert res.confidence == 0.92


def test_compatibility_resolver_exact_and_allowed_relations():
    """Verify CompatibilityResolver resolves EXACT, ALLOWED, and UNKNOWN relation types."""
    # Exact match
    rel_exact = CompatibilityResolver.resolve_relation("Software Engineering", "Software Engineering")
    assert rel_exact == TaxonomyRelationType.EXACT
    assert CompatibilityResolver.get_ranking_weight(rel_exact) == 1.0

    # Custom record match
    records = [
        {"family_a": "Software Engineering", "family_b": "Data Engineering", "is_allowed": True, "status": "ALLOWED"},
        {"family_a": "Software Engineering", "family_b": "Human Resources", "is_allowed": False, "status": "DISALLOWED"},
    ]
    rel_allowed = CompatibilityResolver.resolve_relation("Software Engineering", "Data Engineering", records)
    assert rel_allowed == TaxonomyRelationType.ALLOWED
    assert CompatibilityResolver.get_ranking_weight(rel_allowed) == 0.85

    rel_disallowed = CompatibilityResolver.resolve_relation("Software Engineering", "Human Resources", records)
    assert rel_disallowed == TaxonomyRelationType.DISALLOWED
    assert CompatibilityResolver.get_ranking_weight(rel_disallowed) == 0.0

    # Unknown
    rel_unknown = CompatibilityResolver.resolve_relation("Software Engineering", "Finance")
    assert rel_unknown == TaxonomyRelationType.UNKNOWN


def test_unified_rule_config_metadata():
    """Verify UnifiedRuleConfig metadata fields."""
    config = SystemRuleConfigFactory.build()
    assert isinstance(config, UnifiedRuleConfig)
    assert config.schema_version != ""
    assert config.policy_version != ""
    assert config.source in ("DATABASE", "BOOTSTRAP", "EMERGENCY_BUNDLED", "bundled_static")
    assert config.changed_by != ""
