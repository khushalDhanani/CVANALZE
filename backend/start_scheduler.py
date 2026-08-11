from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from rq.cron import CronScheduler

from app.core.background_tasks import run_integration_sync, snapshot_validation_metrics
from app.core.config import settings
from app.core.logging import logger


class ResilientCronScheduler(CronScheduler):
    """Allow a clean shutdown when Redis stops before the scheduler."""

    def register_death(self, pipeline=None) -> None:
        try:
            super().register_death(pipeline)
        except RedisConnectionError as exc:
            logger.warning("Could not unregister RQ cron scheduler during shutdown because Redis is unavailable: %s", exc)


def register_recurring_jobs(scheduler: CronScheduler) -> int:
    """Register enabled recurring jobs and return their count."""
    registered = 0
    if settings.BACKGROUND_SYNC_ENABLED:
        scheduler.register(
            run_integration_sync,
            queue_name=settings.RQ_AUXILIARY_QUEUE_NAME,
            interval=settings.BACKGROUND_SYNC_INTERVAL_SECONDS,
            job_timeout=settings.BACKGROUND_SYNC_JOB_TIMEOUT_SECONDS,
            result_ttl=settings.RQ_RESULT_TTL_SECONDS,
        )
        registered += 1

    if settings.VALIDATION_METRICS_SNAPSHOT_ENABLED:
        scheduler.register(
            snapshot_validation_metrics,
            queue_name=settings.RQ_SHADOW_QUEUE_NAME,
            interval=settings.VALIDATION_METRICS_SNAPSHOT_INTERVAL_SECONDS,
            job_timeout=settings.RQ_JOB_TIMEOUT_SECONDS,
            result_ttl=settings.RQ_RESULT_TTL_SECONDS,
        )
        registered += 1

    return registered


def main() -> None:
    redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
    scheduler = ResilientCronScheduler(connection=Redis.from_url(redis_url), logging_level="INFO")
    registered = register_recurring_jobs(scheduler)
    if registered == 0:
        logger.warning("No recurring background jobs are enabled; scheduler will not start.")
        return
    logger.info("Starting RQ cron scheduler with %s recurring job(s).", registered)
    scheduler.start()


if __name__ == "__main__":
    main()
