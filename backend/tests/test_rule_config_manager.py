import copy

import pytest

from app.core.rule_config_manager import RuleConfigManager


def test_rule_config_manager_loads_valid_default_config():
    config = RuleConfigManager.load_config()
    assert config is not None
    assert config.version == "1.1.0"
    assert "location" in config.fields
    assert "name" in config.fields
    assert "job_title" in config.fields
    assert "company_name" in config.fields
    assert "scoring" in config.model_dump()

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


def test_scoring_accessors_expose_data_driven_rules():
    match_rules = RuleConfigManager.get_match_rules()
    assert "team" in match_rules.domain_department_denylist
    assert "work experience" in match_rules.cv_section_heading_denylist
    assert "skills" in match_rules.cv_section_heading_compact_denylist
    assert "contact" in match_rules.cv_section_heading_substring_denylist
    assert match_rules.fallback_defaults.recommended_department == "General Engineering & Operations"
    assert "widgets" in match_rules.term_matching.aliases
    assert "flutter developer" in match_rules.cross_domain_guard.software_candidate_keywords
    assert match_rules.cross_domain_guard.domain_mismatch_multiplier == 0.15

    prefilter = RuleConfigManager.get_prefilter_rules()
    assert "senior" in prefilter.stop_words
    assert prefilter.lexical_weights.department_match == 30.0
    assert prefilter.lexical_weights.title_term_match == 15.0
    assert prefilter.rrf_k_constant == 60.0

    taxonomy = RuleConfigManager.get_taxonomy_rules()
    assert taxonomy.default_domain == "General Operations"
    assert taxonomy.default_family == "General Professional"
    assert "Software Engineering & Development" in taxonomy.compatibility_map
    assert len(taxonomy.vacancy_rules) == 14
    assert len(taxonomy.candidate_rules) == 7

    resume_quality = RuleConfigManager.get_resume_quality_rules()
    assert set(resume_quality.core_sections) == {"contact", "summary", "experience", "education", "skills"}
    assert resume_quality.density_scores[0].min_words_per_page == 150
    assert len(resume_quality.section_patterns) == 7
    assert len(resume_quality.heading_normalization) == 5

    domain_embedding = RuleConfigManager.get_domain_embedding_rules()
    assert "skills" in domain_embedding.categories
    assert domain_embedding.canonical_equivalents["skills"]["postgres"] == "postgresql"


def test_term_matching_assets_are_cached_and_normalized():
    assets = RuleConfigManager.get_term_matching_assets()
    assert assets["stop_phrases"] == {"e.g", "eg", "e.g.", "etc", "etc.", "i.e", "i.e."}
    assert "the" in assets["noise_words"]
    assert assets["aliases"]["restful apis"] == ["api", "apis", "rest", "restful", "http"]
    assert RuleConfigManager.get_term_matching_assets() is assets


def test_cross_domain_guard_assets_are_normalized():
    assets = RuleConfigManager.get_cross_domain_guard_assets()
    assert "full stack developer" in assets["software_candidate_keywords"]
    assert "human resources" in assets["non_it_job_keywords"]
    assert assets["domain_guard_terms"]["finance"] == {"finance", "account", "audit", "tax", "ledger"}


def test_compiled_regex_cache_normalizes_headings_and_detects_sections():
    text = "##   work experience"
    for pattern, replacement in RuleConfigManager.get_compiled_heading_normalizations():
        text = pattern.sub(replacement, text)
    assert text == "## WORK EXPERIENCE"

    patterns = RuleConfigManager.get_compiled_section_patterns()
    assert patterns["skills"].search("Technical Skills")
    assert not patterns["skills"].search("no section here")


def test_cache_invalidation_on_config_reload():
    assets_before = RuleConfigManager.get_term_matching_assets()
    assert "widgets" in assets_before["aliases"]

    raw_dict = RuleConfigManager.get_config().model_dump()
    candidate_dict = copy.deepcopy(raw_dict)
    candidate_dict["scoring"]["match"]["term_matching"]["aliases"]["widgets"] = ["widget"]

    RuleConfigManager.load_config(candidate_dict)
    assets_after = RuleConfigManager.get_term_matching_assets()
    assert assets_after["aliases"]["widgets"] == ["widget"]
    assert assets_after is not assets_before

    RuleConfigManager.load_config()


def test_taxonomy_invariant_rejects_unknown_compatibility_family():
    raw_dict = RuleConfigManager.get_config().model_dump()
    candidate_dict = copy.deepcopy(raw_dict)
    candidate_dict["scoring"]["taxonomy"]["compatibility_map"]["Software Engineering & Development"] = ["Not A Real Family"]

    with pytest.raises(ValueError, match=r"SAFETY_GATE_VIOLATION.*unknown family"):
        RuleConfigManager.load_config(candidate_dict)

    RuleConfigManager.load_config()


def test_taxonomy_invariant_rejects_unknown_rule_domain():
    raw_dict = RuleConfigManager.get_config().model_dump()
    candidate_dict = copy.deepcopy(raw_dict)
    candidate_dict["scoring"]["taxonomy"]["vacancy_rules"][0]["domain"] = "Bogus Domain"

    with pytest.raises(ValueError, match=r"SAFETY_GATE_VIOLATION.*unknown domain"):
        RuleConfigManager.load_config(candidate_dict)

    RuleConfigManager.load_config()


def test_resume_quality_invariant_rejects_unordered_density_tiers():
    raw_dict = RuleConfigManager.get_config().model_dump()
    candidate_dict = copy.deepcopy(raw_dict)
    candidate_dict["scoring"]["resume_quality"]["density_scores"] = [
        {"min_words_per_page": 30, "score": 0.10},
        {"min_words_per_page": 150, "score": 0.25},
    ]

    with pytest.raises(ValueError, match=r"SAFETY_GATE_VIOLATION.*ordered by descending"):
        RuleConfigManager.load_config(candidate_dict)

    RuleConfigManager.load_config()


def test_rule_config_manager_metrics_and_reload():
    RuleConfigManager.load_config()
    metrics = RuleConfigManager.get_metrics()

    assert metrics["config_version"] == "1.1.0"
    assert metrics["config_load_count"] >= 1
    assert metrics["compiled_pattern_count"] > 0
    assert metrics["config_load_time_ms"] >= 0.0
    assert metrics["cache_build_time_ms"] >= 0.0

    reloaded = RuleConfigManager.reload_if_changed()
    assert reloaded is False


