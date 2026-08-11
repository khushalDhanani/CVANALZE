from unittest.mock import patch

from app.core.error_handlers import SystemConfigurationError
from app.core.rule_config_readiness import try_load_active_rule_config, wait_for_active_rule_config


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
