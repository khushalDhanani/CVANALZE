from __future__ import annotations

import time

from app.core.config import settings
from app.core.error_handlers import SystemConfigurationError
from app.core.logging import logger
from app.core.rule_config_manager import RuleConfigManager
from app.services.prompt_service import PromptService

RUNTIME_READY = "READY"
RULE_CONFIG_NOT_READY = "RULE_CONFIG_NOT_READY"
PROMPT_NOT_READY = "PROMPT_NOT_READY"
TAXONOMY_NOT_READY = "TAXONOMY_NOT_READY"


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


def cv_runtime_readiness(*, process_name: str, log_unavailable: bool = True) -> str:
    """Return the first dependency that prevents safe CV dequeue."""
    if not try_load_active_rule_config(process_name=process_name, log_unavailable=log_unavailable):
        return RULE_CONFIG_NOT_READY
    prompt_readiness = PromptService.check_required_optimized_match_prompt()
    if not prompt_readiness.ready:
        if log_unavailable:
            logger.warning(
                "[%s] PROMPT_NOT_READY: %s The CV worker will remain idle.",
                process_name,
                prompt_readiness.reason,
            )
        return PROMPT_NOT_READY
    from app.repositories.department_domain import department_domain_repository

    if not department_domain_repository.is_ready():
        if log_unavailable:
            logger.warning(
                "[%s] TAXONOMY_NOT_READY: Required taxonomy/domain configuration contains zero active domains. The CV worker will remain idle.",
                process_name,
            )
        return TAXONOMY_NOT_READY
    return RUNTIME_READY


def wait_for_cv_runtime_dependencies(*, process_name: str, on_wait=None) -> None:
    """Keep a CV worker alive and idle until rules and its required prompt are valid."""
    log_unavailable = True
    while cv_runtime_readiness(process_name=process_name, log_unavailable=log_unavailable) != RUNTIME_READY:
        log_unavailable = False
        if on_wait is not None:
            on_wait()
        time.sleep(settings.RULE_CONFIG_RETRY_INTERVAL_SECONDS)
