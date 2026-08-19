import os
import sys

# Fix for macOS fork() issue with PyTorch/CoreFoundation
# We must restart the process via execv to ensure the C-level env is set before any libraries load
if os.environ.get("OBJC_DISABLE_INITIALIZE_FORK_SAFETY") != "YES":
    os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
    os.execv(sys.executable, [sys.executable] + sys.argv)

from redis import Redis
from rq import Queue, Worker
from rq.intermediate_queue import IntermediateQueue

from app.core.config import settings
from app.core.config_listener import start_config_invalidation_listener
from app.core.logging import logger
from app.core.rq_worker_identity import build_rq_worker_name
from app.core.rule_config_readiness import RUNTIME_READY, cv_runtime_readiness, wait_for_cv_runtime_dependencies
from app.services.processing_queue import handle_work_horse_killed


class RuntimeDependencyWorker(Worker):
    """Gate each dequeue so runtime configuration changes fail closed."""

    def dequeue_job_and_maintain_ttl(self, timeout, max_idle_time=None):
        while True:
            wait_for_cv_runtime_dependencies(process_name="CV_WORKER", on_wait=self.heartbeat)
            result = super().dequeue_job_and_maintain_ttl(timeout, max_idle_time)
            if result is None or cv_runtime_readiness(process_name="CV_WORKER", log_unavailable=False) == RUNTIME_READY:
                return result
            job, queue = result
            pipeline = self.connection.pipeline()
            pipeline.lrem(IntermediateQueue(queue.key, self.connection).key, 1, job.id)
            pipeline.lpush(queue.key, job.id)
            pipeline.execute()
            logger.warning("[CV_WORKER] Runtime dependency changed during dequeue; restored job '%s' to the FIFO front.", job.id)


def main():
    if settings.CV_PROCESSING_CONCURRENCY != 1:
        raise RuntimeError("CV_PROCESSING_CONCURRENCY must be 1.")
    redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
    conn = Redis.from_url(redis_url)
    wait_for_cv_runtime_dependencies(process_name="CV_WORKER")
    start_config_invalidation_listener()

    queue = Queue(settings.RQ_QUEUE_NAME, connection=conn)
    worker_name = build_rq_worker_name(f"{settings.RQ_QUEUE_NAME}-worker")
    logger.info("Starting single-slot RQ CV worker '%s' on queue '%s'.", worker_name, settings.RQ_QUEUE_NAME)
    worker = RuntimeDependencyWorker(
        [queue],
        connection=conn,
        name=worker_name,
        maintenance_interval=settings.RQ_MAINTENANCE_INTERVAL_SECONDS,
        work_horse_killed_handler=handle_work_horse_killed,
    )
    work_options: dict[str, bool | int] = {
        "with_scheduler": True,
    }
    if settings.RQ_WORKER_MAX_JOBS > 0:
        work_options["max_jobs"] = settings.RQ_WORKER_MAX_JOBS
    worker.work(**work_options)


if __name__ == "__main__":
    main()
