import time

from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from rq.cron import CronJob, CronScheduler

from app.core.background_tasks import reconcile_cv_processing_jobs, run_integration_sync, snapshot_validation_metrics
from app.core.config import settings
from app.core.logging import logger

_TRANSIENT_REDIS_ERRORS = (RedisConnectionError, RedisTimeoutError)


class ResilientCronScheduler(CronScheduler):
    """Keep recurring scheduling alive through transient Redis failures."""

    def _record_redis_failure(self, operation: str, exc: RedisConnectionError | RedisTimeoutError) -> None:
        self._redis_retry_after = (
            time.monotonic() + settings.SCHEDULER_REDIS_RETRY_DELAY_SECONDS
        )
        logger.warning("RQ cron scheduler could not %s because Redis is unavailable; retrying: %s", operation, exc)

    def enqueue_jobs(self) -> list[CronJob]:
        try:
            enqueued_jobs = super().enqueue_jobs()
            self._redis_retry_after = None
            return enqueued_jobs
        except _TRANSIENT_REDIS_ERRORS as exc:
            self._record_redis_failure("enqueue recurring jobs", exc)
            return []

    def save_jobs_data(self) -> None:
        try:
            super().save_jobs_data()
        except _TRANSIENT_REDIS_ERRORS as exc:
            self._record_redis_failure("save recurring job state", exc)

    def heartbeat(self) -> None:
        try:
            super().heartbeat()
        except _TRANSIENT_REDIS_ERRORS as exc:
            self._record_redis_failure("send its heartbeat", exc)

    def calculate_sleep_interval(self) -> float:
        sleep_interval = super().calculate_sleep_interval()
        retry_after = getattr(self, "_redis_retry_after", None)
        if retry_after is None:
            return sleep_interval
        return max(sleep_interval, max(0.0, retry_after - time.monotonic()))

    def register_death(self, pipeline=None) -> None:
        try:
            super().register_death(pipeline)
        except _TRANSIENT_REDIS_ERRORS as exc:
            logger.warning("Could not unregister RQ cron scheduler during shutdown because Redis is unavailable: %s", exc)


def register_recurring_jobs(scheduler: CronScheduler) -> int:
    """Register enabled recurring jobs and return their count."""
    registered = 0
    if settings.CV_JOB_RECONCILIATION_INTERVAL_SECONDS > 0:
        scheduler.register(
            reconcile_cv_processing_jobs,
            queue_name=settings.RQ_AUXILIARY_QUEUE_NAME,
            interval=settings.CV_JOB_RECONCILIATION_INTERVAL_SECONDS,
            job_timeout=settings.RQ_JOB_TIMEOUT_SECONDS,
            result_ttl=settings.RQ_RESULT_TTL_SECONDS,
        )
        registered += 1

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
    if not settings.REDIS_URL:
        raise RuntimeError("REDIS_URL is required to start the scheduler.")
    redis_conn = Redis.from_url(
        settings.REDIS_URL,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
        socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
        socket_keepalive=True,
        retry_on_timeout=True,
        health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS,
    )
    scheduler = ResilientCronScheduler(connection=redis_conn, logging_level="INFO")
    registered = register_recurring_jobs(scheduler)
    if registered == 0:
        logger.warning("No recurring background jobs are enabled; scheduler will not start.")
        return
    logger.info("Starting RQ cron scheduler with %s recurring job(s).", registered)
    scheduler.start()


if __name__ == "__main__":
    main()
