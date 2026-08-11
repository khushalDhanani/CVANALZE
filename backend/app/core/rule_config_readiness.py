from __future__ import annotations

import time

from app.core.config import settings
from app.core.error_handlers import SystemConfigurationError
from app.core.logging import logger
from app.core.rule_config_manager import RuleConfigManager


def try_load_active_rule_config(*, process_name: str, log_unavailable: bool = True) -> bool:
    """Load the active database configuration without terminating the control plane."""
    try:
        RuleConfigManager.load_config(tenant_id=None)
        logger.info("[%s] Active PostgreSQL rule configuration loaded and validated.", process_name)
        return True
    except SystemConfigurationError:
        if log_unavailable:
            logger.warning(
                "[%s] No active PostgreSQL rule configuration is available. "
                "The process will remain fail-closed until an administrator activates one.",
                process_name,
            )
    except Exception as exc:
        if log_unavailable:
            logger.error(
                "[%s] Active PostgreSQL rule configuration is invalid or unavailable: %s",
                process_name,
                type(exc).__name__,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
    return False


def wait_for_active_rule_config(*, process_name: str) -> None:
    """Keep an RQ worker alive but idle until its database configuration is valid."""
    log_unavailable = True
    while not try_load_active_rule_config(process_name=process_name, log_unavailable=log_unavailable):
        log_unavailable = False
        time.sleep(settings.RULE_CONFIG_RETRY_INTERVAL_SECONDS)
