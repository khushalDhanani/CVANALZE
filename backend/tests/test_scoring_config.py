from unittest.mock import patch

from app.schemas.scoring_config import (
    DEFAULT_COMPONENT_WEIGHTS,
    DEFAULT_LLM_SEMANTIC_WEIGHT,
    DEFAULT_MATCH_HIGH_THRESHOLD,
    DEFAULT_MATCH_MEDIUM_THRESHOLD,
    DEFAULT_MAX_LLM_BOOST,
    DEFAULT_MAX_SCORE_ON_FAILURE,
    DEFAULT_PENALTY_PER_ITEM,
    DEFAULT_PERFECT_COMPONENT_SCORE,
    DEFAULT_REJECTION_SCORE_EPSILON,
    DEFAULT_ZERO_SKILLS_SCORE_CAP,
    ScoringConfig,
)


def test_scoring_config_defaults_integrity():
    """Verify default constants are consistent and weights sum to 1.0."""
    cfg = ScoringConfig()
    assert sum(DEFAULT_COMPONENT_WEIGHTS.values()) == 1.0
    assert cfg.perfect_component_score == DEFAULT_PERFECT_COMPONENT_SCORE
    assert cfg.penalty_per_item == DEFAULT_PENALTY_PER_ITEM
    assert cfg.max_score_on_failure == DEFAULT_MAX_SCORE_ON_FAILURE
    assert cfg.llm_semantic_weight == DEFAULT_LLM_SEMANTIC_WEIGHT
    assert cfg.max_llm_boost == DEFAULT_MAX_LLM_BOOST
    assert cfg.match_high_threshold == DEFAULT_MATCH_HIGH_THRESHOLD
    assert cfg.match_medium_threshold == DEFAULT_MATCH_MEDIUM_THRESHOLD
    assert cfg.zero_skills_score_cap == DEFAULT_ZERO_SKILLS_SCORE_CAP
    assert cfg.rejection_score_epsilon == DEFAULT_REJECTION_SCORE_EPSILON
    assert cfg.calculate_rejection_cap() == 49.9
    assert cfg.component_weights == DEFAULT_COMPONENT_WEIGHTS
    assert cfg.profile_code == "DEFAULT"
    assert not cfg.is_fallback


def test_scoring_config_override_branch():
    """Verify override_config passes custom values and marks profile as OVERRIDE."""
    custom_overrides = {
        "MANDATORY_FAILURE_PENALTY_PER_ITEM": 25.0,
        "MAX_SCORE_ON_MANDATORY_FAILURE": 40.0,
        "LLM_SEMANTIC_WEIGHT": 0.20,
        "MAX_LLM_BOOST": 12.0,
        "MATCH_HIGH_THRESHOLD": 85.0,
        "MATCH_MEDIUM_THRESHOLD": 60.0,
        "ZERO_SKILLS_SCORE_CAP": 65.0,
        "REJECTION_SCORE_EPSILON": 0.05,
        "MATCH_COMPONENT_WEIGHTS": {
            "role": 0.20,
            "skills": 0.30,
            "experience": 0.20,
            "education": 0.10,
            "domain": 0.10,
            "technology": 0.05,
            "certification": 0.025,
            "responsibilities": 0.025,
        },
    }
    cfg = ScoringConfig.load(override_config=custom_overrides)
    assert cfg.profile_code == "OVERRIDE"
    assert cfg.profile_version == "custom"
    assert cfg.penalty_per_item == 25.0
    assert cfg.max_score_on_failure == 40.0
    assert cfg.llm_semantic_weight == 0.20
    assert cfg.max_llm_boost == 12.0
    assert cfg.match_high_threshold == 85.0
    assert cfg.match_medium_threshold == 60.0
    assert cfg.zero_skills_score_cap == 65.0
    assert cfg.rejection_score_epsilon == 0.05
    assert cfg.calculate_rejection_cap() == 60.0 - 0.05
    assert cfg.component_weights["skills"] == 0.30
    assert not cfg.is_fallback


def test_scoring_config_load_active_rule_config():
    """Verify load() succeeds when RuleConfigManager is initialized."""
    from app.core.rule_config_manager import RuleConfigManager
    # Ensure config is initialized
    if not RuleConfigManager.is_config_loaded():
        RuleConfigManager.load_config()

    cfg = ScoringConfig.load()
    assert cfg.profile_code in ("DEFAULT", "v1.1.0", "custom") or len(cfg.profile_code) > 0
    assert cfg.match_high_threshold > 0.0
    assert cfg.match_medium_threshold > 0.0
    assert cfg.zero_skills_score_cap == 40.0
    assert len(cfg.component_weights) > 0
    assert not cfg.is_fallback


def test_scoring_config_fallback_to_in_memory_rule_config_on_db_error():
    """Verify that when DynamicScoringAndPrefilterService DB query fails, active in-memory params are preserved."""
    from app.core.rule_config_manager import RuleConfigManager
    if not RuleConfigManager.is_config_loaded():
        RuleConfigManager.load_config()

    with patch(
        "app.services.dynamic_scoring_prefilter_service.DynamicScoringAndPrefilterService.get_tenant_scoring_profile",
        side_effect=RuntimeError("Database connection lost"),
    ):
        cfg = ScoringConfig.load()
        # Should gracefully use in-memory RuleConfigManager instead of degrading to FALLBACK
        assert cfg.profile_code == "DEFAULT"
        assert not cfg.is_fallback
        assert cfg.match_high_threshold == RuleConfigManager.get_scoring_parameters().match_high_threshold


def test_scoring_config_absolute_fallback_when_uninitialized():
    """Verify that when all providers fail, it returns FALLBACK with is_fallback=True."""
    with patch(
        "app.services.dynamic_scoring_prefilter_service.DynamicScoringAndPrefilterService.get_tenant_scoring_profile",
        side_effect=RuntimeError("Total outage"),
    ), patch(
        "app.core.rule_config_manager.RuleConfigManager.is_config_loaded",
        return_value=False,
    ), patch(
        "app.core.rule_config_manager.RuleConfigManager.get_scoring_parameters",
        side_effect=RuntimeError("No in-memory cache"),
    ):
        cfg = ScoringConfig.load()
        assert cfg.profile_code == "FALLBACK"
        assert cfg.profile_version == "v0"
        assert cfg.is_fallback
        assert cfg.match_high_threshold == DEFAULT_MATCH_HIGH_THRESHOLD
        assert cfg.zero_skills_score_cap == DEFAULT_ZERO_SKILLS_SCORE_CAP
        assert cfg.component_weights == DEFAULT_COMPONENT_WEIGHTS


def test_zero_skills_score_cap_is_configurable_in_evaluator():
    """Verify ComponentScoreEvaluator adheres to configurable zero_skills_score_cap when skills match is 0.0%."""
    from app.schemas.candidate_context import CandidateAnalysisContext
    from app.schemas.job_context import JobEvaluationContext
    from app.services.match_evaluators import ComponentScoreEvaluator, RequirementEvaluationResults

    cand_ctx = CandidateAnalysisContext(
        cv_text="experienced backend engineer with leadership experience",
        norm_text="experienced backend engineer with leadership experience",
        domain_candidate_text="it software engineering",
        cand_domain="IT & Software Services",
        cand_families=["Software Engineering & Development"],
        current_role="Software Engineer",
        experience_titles=["Software Engineer"],
        professional_skills=["leadership"],
    )
    job_ctx = JobEvaluationContext.create(
        {
            "id": "job_1",
            "title": "Software Engineer",
            "department": "IT & Software Services",
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
        }
    )

    req_results = RequirementEvaluationResults()

    # 1. Default cap at 40.0 (55.6 is capped down to 40.0)
    default_cfg = ScoringConfig()
    result_default = ComponentScoreEvaluator.evaluate(
        context=cand_ctx,
        job=job_ctx,
        req_results=req_results,
        transition_detected=False,
        common_words=set(),
        extract_term_matches_fn=lambda text, terms: ([], []),
        scoring_config=default_cfg,
    )
    assert result_default.skills_score == 0.0
    assert result_default.final_score == 40.0
    assert "Capped score due to 0% skills match" in result_default.reason_str

    # 2. Custom cap at 50.0 (55.6 is capped down to 50.0)
    custom_cfg = ScoringConfig(zero_skills_score_cap=50.0)
    result_custom = ComponentScoreEvaluator.evaluate(
        context=cand_ctx,
        job=job_ctx,
        req_results=req_results,
        transition_detected=False,
        common_words=set(),
        extract_term_matches_fn=lambda text, terms: ([], []),
        scoring_config=custom_cfg,
    )
    assert result_custom.skills_score == 0.0
    assert result_custom.final_score == 50.0
    assert "cap: 50.0%" in result_custom.reason_str

    # 3. Higher cap at 60.0 (55.6 is below 60.0, so no capping occurs)
    uncapped_cfg = ScoringConfig(zero_skills_score_cap=60.0)
    result_uncapped = ComponentScoreEvaluator.evaluate(
        context=cand_ctx,
        job=job_ctx,
        req_results=req_results,
        transition_detected=False,
        common_words=set(),
        extract_term_matches_fn=lambda text, terms: ([], []),
        scoring_config=uncapped_cfg,
    )
    assert result_uncapped.skills_score == 0.0
    assert result_uncapped.final_score == 55.6
    assert "Capped score due to 0% skills match" not in result_uncapped.reason_str
