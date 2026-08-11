from redis import Redis
from rq import Queue, Worker

from app.core.config import settings
from app.core.config_listener import start_config_invalidation_listener
from app.core.logging import logger
from app.core.rule_config_manager import RuleConfigManager


def main() -> None:
    redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
    connection = Redis.from_url(redis_url)
    RuleConfigManager.load_config(tenant_id=None)
    start_config_invalidation_listener()
    queue_names = list(dict.fromkeys([settings.RQ_AUXILIARY_QUEUE_NAME, settings.RQ_SHADOW_QUEUE_NAME]))
    queues = [Queue(name, connection=connection) for name in queue_names]
    logger.info("Starting auxiliary RQ worker on queues: %s", ", ".join(queue_names))
    Worker(queues, connection=connection, name="cv-analyzer-auxiliary-worker").work(
        with_scheduler=True,
        maintenance_interval=settings.RQ_MAINTENANCE_INTERVAL_SECONDS,
    )


if __name__ == "__main__":
    main()
