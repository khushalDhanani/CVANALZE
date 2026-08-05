import threading
import time

from app.core.cache import RedisCache
from app.core.logging import logger
from app.core.rule_config_manager import RuleConfigManager
from app.services.configuration_service import ConfigurationService


def config_invalidation_worker():
    """Background thread that listens for configuration invalidation events."""
    while True:
        try:
            client = RedisCache._get_client()
            if not client:
                time.sleep(5)
                continue

            pubsub = client.pubsub()
            pubsub.subscribe(ConfigurationService.REDIS_PUBSUB_CHANNEL)
            logger.info("[CONFIG] Started listening for configuration invalidation events.")

            for message in pubsub.listen():
                if message["type"] == "message":
                    tenant_or_global = message["data"]
                    if isinstance(tenant_or_global, bytes):
                        tenant_or_global = tenant_or_global.decode("utf-8")
                        
                    logger.info(f"[CONFIG] Received invalidation event for: {tenant_or_global}")
                    
                    try:
                        if tenant_or_global == "GLOBAL":
                            RuleConfigManager.load_config(tenant_id=None)
                        else:
                            RuleConfigManager.load_config(tenant_id=tenant_or_global)
                    except Exception as e:
                        logger.error(f"[CONFIG] Failed to reload config for {tenant_or_global}: {e}")
                        
        except Exception as e:
            logger.warning(f"[CONFIG] Invalidation listener error: {e}. Retrying in 5s...")
            time.sleep(5)


def start_config_invalidation_listener():
    """Starts the Redis Pub/Sub listener in a daemon thread."""
    thread = threading.Thread(target=config_invalidation_worker, daemon=True, name="ConfigInvalidationListener")
    thread.start()
