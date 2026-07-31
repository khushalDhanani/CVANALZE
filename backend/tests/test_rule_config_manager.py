import copy
import pytest
from app.core.rule_config_manager import RuleConfigManager, UnifiedRuleConfig


def test_rule_config_manager_loads_valid_default_config():
    config = RuleConfigManager.load_config()
    assert config is not None
    assert config.version == "1.0.0"
    assert "location" in config.fields
    assert "name" in config.fields
    assert "job_title" in config.fields
    assert "company_name" in config.fields

    loc_cfg = RuleConfigManager.get_field_config("location")
    assert loc_cfg.tier_thresholds.high_min == 0.80
    assert loc_cfg.downstream_gates.min_acceptance_confidence == 0.50
    assert "surat" in RuleConfigManager.get_keywords("location", "gazetteer")


def test_rule_config_manager_enforces_override_reason_invariant():
    raw_dict = RuleConfigManager.get_config().model_dump()
    candidate_dict = copy.deepcopy(raw_dict)

    # Deviate location high_min to 0.85 without override_reason
    candidate_dict["fields"]["location"]["tier_thresholds"]["high_min"] = 0.85
    candidate_dict["fields"]["location"]["tier_thresholds"]["override_reason"] = None

    with pytest.raises(ValueError, match=r"SAFETY_GATE_VIOLATION.*override_reason is missing"):
        RuleConfigManager.load_config(candidate_dict)

    # Providing valid override_reason allows it to pass
    candidate_dict["fields"]["location"]["tier_thresholds"]["override_reason"] = "Location gazetteer match requires 0.85"
    loaded = RuleConfigManager.load_config(candidate_dict)
    assert loaded.fields["location"].tier_thresholds.high_min == 0.85

    # Restore default config
    RuleConfigManager.load_config()


def test_rule_config_manager_enforces_email_fallback_safety_invariant():
    raw_dict = RuleConfigManager.get_config().model_dump()
    candidate_dict = copy.deepcopy(raw_dict)

    # Set min_acceptance_confidence to 0.30 (equal to email_username_fallback)
    candidate_dict["fields"]["name"]["downstream_gates"]["min_acceptance_confidence"] = 0.30

    with pytest.raises(ValueError, match=r"SAFETY_GATE_VIOLATION.*must be strictly greater than email_username_fallback"):
        RuleConfigManager.load_config(candidate_dict)

    # Restore default config
    RuleConfigManager.load_config()


def test_rule_config_manager_enforces_medium_min_decoupling_invariant():
    raw_dict = RuleConfigManager.get_config().model_dump()
    candidate_dict = copy.deepcopy(raw_dict)

    # Raise medium_min (0.60) above min_acceptance_confidence (0.50)
    candidate_dict["fields"]["location"]["tier_thresholds"]["medium_min"] = 0.60
    candidate_dict["fields"]["location"]["downstream_gates"]["min_acceptance_confidence"] = 0.50
    candidate_dict["fields"]["location"]["tier_thresholds"]["override_reason"] = "Higher medium threshold"

    with pytest.raises(ValueError, match=r"SAFETY_GATE_VIOLATION.*cannot be lower than medium_min threshold"):
        RuleConfigManager.load_config(candidate_dict)

    # Restore default config
    RuleConfigManager.load_config()


def test_rule_config_manager_synthetic_smoke_tests_pass():
    config = RuleConfigManager.get_config()
    # Smoke tests run automatically during load_config and pass clean
    RuleConfigManager._run_synthetic_smoke_tests(config)


def test_get_confidence_tier_calculation():
    assert RuleConfigManager.get_confidence_tier("name", 0.90) == "HIGH"
    assert RuleConfigManager.get_confidence_tier("name", 0.55) == "MEDIUM"
    assert RuleConfigManager.get_confidence_tier("name", 0.30) == "LOW"
    assert RuleConfigManager.get_confidence_tier("name", None) == "LOW"

    assert RuleConfigManager.get_confidence_tier("location", 0.90) == "HIGH"
    assert RuleConfigManager.get_confidence_tier("location", 0.50) == "MEDIUM"
    assert RuleConfigManager.get_confidence_tier("location", 0.10) == "LOW"

    assert RuleConfigManager.get_confidence_tier("job_title", 0.85) == "HIGH"
    assert RuleConfigManager.get_confidence_tier("company_name", 0.60) == "MEDIUM"

