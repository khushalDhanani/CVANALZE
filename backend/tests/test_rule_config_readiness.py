from unittest.mock import patch

from app.core.error_handlers import SystemConfigurationError
from app.core.rule_config_readiness import (
    PROMPT_NOT_READY,
    RUNTIME_READY,
    cv_runtime_readiness,
    try_load_active_rule_config,
    wait_for_active_rule_config,
    wait_for_cv_runtime_dependencies,
)
from app.services.prompt_service import PromptReadiness


def test_try_load_active_rule_config_keeps_control_plane_available():
    with patch("app.core.rule_config_readiness.RuleConfigManager.load_config", side_effect=SystemConfigurationError("CONFIGURATION_UNAVAILABLE")):
        assert try_load_active_rule_config(process_name="TEST_API") is False


def test_worker_waits_until_database_configuration_is_active():
    with (
        patch(
            "app.core.rule_config_readiness.RuleConfigManager.load_config",
            side_effect=[SystemConfigurationError("CONFIGURATION_UNAVAILABLE"), object()],
        ) as load_config,
        patch("app.core.rule_config_readiness.time.sleep") as sleep,
    ):
        wait_for_active_rule_config(process_name="TEST_WORKER")

    assert load_config.call_count == 2
    sleep.assert_called_once()


def test_cv_worker_waits_for_required_prompt_after_rules_are_ready():
    with (
        patch("app.core.rule_config_readiness.RuleConfigManager.load_config", return_value=object()),
        patch(
            "app.core.rule_config_readiness.PromptService.check_required_optimized_match_prompt",
            side_effect=[PromptReadiness(False, "missing"), PromptReadiness(True, "READY")],
        ) as check_prompt,
        patch("app.core.rule_config_readiness.time.sleep") as sleep,
    ):
        wait_for_cv_runtime_dependencies(process_name="TEST_WORKER")

    assert check_prompt.call_count == 2
    sleep.assert_called_once()


def test_cv_runtime_readiness_reports_prompt_not_ready():
    with (
        patch("app.core.rule_config_readiness.RuleConfigManager.load_config", return_value=object()),
        patch(
            "app.core.rule_config_readiness.PromptService.check_required_optimized_match_prompt",
            return_value=PromptReadiness(False, "missing"),
        ),
    ):
        assert cv_runtime_readiness(process_name="TEST", log_unavailable=False) == PROMPT_NOT_READY

    with (
        patch("app.core.rule_config_readiness.RuleConfigManager.load_config", return_value=object()),
        patch(
            "app.core.rule_config_readiness.PromptService.check_required_optimized_match_prompt",
            return_value=PromptReadiness(True, "READY"),
        ),
    ):
        assert cv_runtime_readiness(process_name="TEST", log_unavailable=False) == RUNTIME_READY
