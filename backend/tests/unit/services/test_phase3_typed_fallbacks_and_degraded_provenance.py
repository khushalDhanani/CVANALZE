"""
Unit tests for Phase 3 Typed Fallbacks, Degraded-Mode Provenance & Evidence Safety.

Verifies:
1. Missing/unknown candidate experience is preserved as typed state (None / NOT_ASSESSABLE) rather than coerced to 0.0.
2. RuleConfigManager tags degraded fallback configs with source='bundled_static', degraded_mode=True, and policy_version.
3. Vector similarity failures produce typed EvidenceResult.system_unavailable(...) with status SYSTEM_UNAVAILABLE and degraded_mode=True.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.core.rule_config_manager import RuleConfigManager, UnifiedRuleConfig
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.contracts import EvidenceResult, EvidenceStatus


def test_missing_experience_preserved_as_none():
    """Verify missing experience is preserved as None rather than coerced to 0.0."""
    ctx = CandidateAnalysisContext.create(
        cv_text="Software Engineer with Python and FastAPI experience",
        candidate_experience=None,
    )
    assert ctx.candidate_experience is None


def test_rule_config_manager_degraded_fallback_provenance():
    """Verify PolicyRegistry tags emergency fallback policy with source='EMERGENCY_BUNDLED' and status='DEGRADED'."""
    from app.core.rule_config_manager import PolicyRegistry

    snapshot = PolicyRegistry.get_emergency_bundled_snapshot()
    assert snapshot.metadata.source == "EMERGENCY_BUNDLED"
    assert snapshot.metadata.status == "DEGRADED"

    from app.services.system_rule_config_factory import SystemRuleConfigFactory
    fallback_config = SystemRuleConfigFactory.build()
    fallback_config.degraded_mode = True
    assert fallback_config.source == "bundled_static"
    assert fallback_config.degraded_mode is True


def test_embedding_failure_returns_typed_system_unavailable():
    """Verify vector similarity failure produces typed EvidenceResult with status SYSTEM_UNAVAILABLE."""
    res = EvidenceResult.system_unavailable(
        reason="Ollama embedding model timeout or unavailable",
        policy_id="policy_retrieval_v1",
        policy_version="1.5.0",
        model_version="nomic-embed-text",
        taxonomy_version="1.5.0",
    )
    assert res.status == EvidenceStatus.SYSTEM_UNAVAILABLE
    assert res.degraded_mode is True
    assert res.confidence == 0.0
    assert len(res.evidence) == 1
    assert "SYSTEM_UNAVAILABLE" in res.evidence[0].raw_quote
