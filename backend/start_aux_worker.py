from redis import Redis
from rq import Queue, Worker

from app.core.config import settings
from app.core.config_listener import start_config_invalidation_listener
from app.core.logging import logger
from app.core.rq_worker_identity import build_rq_worker_name
from app.core.rule_config_readiness import wait_for_active_rule_config


def main() -> None:
    redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
    connection = Redis.from_url(redis_url)
    wait_for_active_rule_config(process_name="AUXILIARY_WORKER")
    start_config_invalidation_listener()
    queue_names = list(dict.fromkeys([settings.RQ_AUXILIARY_QUEUE_NAME, settings.RQ_SHADOW_QUEUE_NAME]))
    queues = [Queue(name, connection=connection) for name in queue_names]
    worker_name = build_rq_worker_name("cv-analyzer-auxiliary-worker")
    logger.info("Starting auxiliary RQ worker '%s' on queues: %s", worker_name, ", ".join(queue_names))
    Worker(
        queues,
        connection=connection,
        name=worker_name,
        maintenance_interval=settings.RQ_MAINTENANCE_INTERVAL_SECONDS,
    ).work(with_scheduler=True)


if __name__ == "__main__":
    main()
