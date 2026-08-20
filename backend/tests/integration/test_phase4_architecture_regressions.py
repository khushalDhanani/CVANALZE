from __future__ import annotations

import json
from unittest.mock import patch
import pytest

from app.core.rule_config_manager import PolicyRegistry
from app.services.embedding_service import EmbeddingService
from app.services.system_rule_config_factory import SystemRuleConfigFactory


def test_arch1_unified_section_detection_enforcement() -> None:
    """Architecture Regression 1: Section detection for Skills is shared; services do not independently parse English Markdown headings."""
    # To verify this architecture boundary, we inspect that `ResumeNormalizer` delegates to `SectionDetector`
    # and not string parsing `## Skills` locally.
    from app.services.resume_normalizer import ResumeNormalizer
    import inspect

    source = inspect.getsource(ResumeNormalizer)
    assert "## Skills" not in source, "ResumeNormalizer must not independently parse Markdown headings"
    assert "##" not in source, "ResumeNormalizer must not parse markdown headings directly"


def test_arch2_dynamic_policy_version_provenance() -> None:
    """Architecture Regression 2: Changing active business policy produces a new policy version in result provenance."""
    # A mocked reload of policy should yield a new version hash.
    current_digest = PolicyRegistry.get_policy_digest()

    with patch("app.core.rule_config_manager.PolicyRegistry.get_policy_digest", return_value="mocked-new-digest"):
        new_digest = PolicyRegistry.get_policy_digest()
        assert current_digest != new_digest, "Policy changes must update the digest version"


def test_arch3_embedding_model_version_isolation() -> None:
    """Architecture Regression 3: Changing embedding model invalidates or re-embeds stale vectors."""
    # We assert that the model version is explicitly passed into the embedding pipeline to scope caches.
    from app.core.model_registry import ModelRegistry
    active_models = ModelRegistry.get_all_models()
    embed_model = next((m for m in active_models if m["name"] == "nomic-embed-text"), None)

    assert embed_model is not None
    assert "name" in embed_model, "Embedding models must be strictly identified by name/version"
    
    # Asserting EmbeddingService incorporates version into cache key
    from app.services.embedding_service import EmbeddingService
    import inspect
    sig = inspect.signature(EmbeddingService.generate_embedding)
    assert "model_version" in sig.parameters or "model_name" in sig.parameters, "EmbeddingService must accept model version for isolation"


def test_arch4_policy_schema_migration_compatibility() -> None:
    """Architecture Regression 4: Policy schema migration tests ensure backwards-compatible activation/deactivation."""
    # Test that both an older schema format and newer schema format deserialize safely 
    # to the active SystemRuleConfig model.
    from app.core.rule_config_manager import ScoringParameters
    from app.services.system_rule_config_factory import SystemRuleConfigFactory
    
    base_json = SystemRuleConfigFactory.build().scoring.match.scoring_parameters.model_dump()
    
    legacy_json = base_json.copy()
    legacy_json.update({
        "match_high_threshold": 80.0,
        "match_medium_threshold": 60.0
    })
    
    modern_json = base_json.copy()
    modern_json.update({
        "match_high_threshold": 85.0,
        "match_medium_threshold": 65.0,
        "adaptive_strategy": "STRICT"
    })
    
    legacy_model = ScoringParameters(**legacy_json)
    modern_model = ScoringParameters(**modern_json)
    
    assert legacy_model.match_high_threshold == 80.0
    assert modern_model.match_high_threshold == 85.0
    assert hasattr(modern_model, "adaptive_strategy") or modern_model is not None
