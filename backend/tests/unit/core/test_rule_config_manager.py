from __future__ import annotations

import pytest

from app.core.rule_config_manager import RuleConfigManager, UnifiedRuleConfig
from tests.mock_rule_config import MOCK_RULE_CONFIG


def test_unified_rule_config_validation() -> None:
    config = UnifiedRuleConfig.model_validate(MOCK_RULE_CONFIG)
    assert config.version == "1.1.0"
    assert "name" in config.fields
    assert "location" in config.fields
    assert "job_title" in config.fields
    assert "company_name" in config.fields
    assert config.scoring.match is not None
    assert config.scoring.taxonomy is not None


def test_rule_config_manager_load_and_active_get() -> None:
    config = RuleConfigManager.get_config()
    assert config is not None
    assert config.version is not None
    assert RuleConfigManager.is_config_loaded() is True


def test_rule_config_field_accessors() -> None:
    field_cfg = RuleConfigManager.get_field_config("name")
    assert field_cfg is not None
    denylist = field_cfg.get_upper_keyword_set("job_title_denylist")
    assert "ENGINEER" in denylist
    assert "DEVELOPER" in denylist


def test_compiled_regex_cache_built() -> None:
    assets = RuleConfigManager.get_cross_domain_guard_assets()
    assert assets is not None
    assert isinstance(assets, dict) or hasattr(assets, "get")


def test_policy_registry_accessors() -> None:
    from app.core.rule_config_manager import PolicyRegistry

    digest = PolicyRegistry.get_policy_digest()
    assert isinstance(digest, str)
    assert len(digest) == 16

    params = PolicyRegistry.get_scoring_parameters()
    assert params is not None
    assert params.match_high_threshold > 0

    tax_rules = PolicyRegistry.get_taxonomy_rules()
    assert tax_rules is not None
    assert tax_rules.default_domain

    term_assets = PolicyRegistry.get_term_matching_assets()
    assert "noise_words" in term_assets

