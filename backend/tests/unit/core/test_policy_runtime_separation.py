from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.rule_config_manager import PolicyRegistry, RuleConfigManager


def test_runtime_config_isolated_from_policy() -> None:
    """Requirement 2.2: Runtime/Infrastructure config (Settings) must be cleanly separated from versioned business policy."""
    settings = Settings()

    # Runtime/Infra attributes belong in Settings
    assert hasattr(settings, "REDIS_URL")
    assert hasattr(settings, "PROJECT_NAME")
    assert hasattr(settings, "RQ_QUEUE_NAME")
    assert hasattr(settings, "CV_PROCESSING_CONCURRENCY")
    assert hasattr(settings, "RATE_LIMIT_REQUESTS")

    # Business policy parameters MUST NOT be present as raw ambient fields in Settings
    assert not hasattr(settings, "scoring_weights")
    assert not hasattr(settings, "mandatory_penalty")
    assert not hasattr(settings, "overqualification_penalty")


def test_business_policy_versioned_and_digested() -> None:
    """Requirement 2.2: Business policy must be versioned, SHA-256 digested, and independent of runtime infra settings."""
    digest_orig = PolicyRegistry.get_policy_digest()
    assert digest_orig is not None
    assert len(digest_orig) == 16

    # Verify business policy contains scoring config, fields, and workflow
    config = RuleConfigManager.get_config()
    assert config.scoring is not None
    assert config.fields is not None
    assert config.version is not None


def test_policy_digest_invariant_under_runtime_infra_changes() -> None:
    """Requirement 2.2: Infrastructure setting changes do not alter business policy version digests."""
    digest_before = PolicyRegistry.get_policy_digest()

    # Simulate runtime infrastructure config update (e.g. changing project name or log level)
    settings = Settings(PROJECT_NAME="CV Analyzer Staging", LOG_LEVEL="DEBUG")

    digest_after = PolicyRegistry.get_policy_digest()

    assert settings.PROJECT_NAME == "CV Analyzer Staging"
    assert digest_before == digest_after, "Policy digest must remain invariant under infrastructure configuration changes."
