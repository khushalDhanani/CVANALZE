import os
import sys

# Fix for macOS fork() issue with PyTorch/CoreFoundation
# We must restart the process via execv to ensure the C-level env is set before any libraries load
if os.environ.get("OBJC_DISABLE_INITIALIZE_FORK_SAFETY") != "YES":
    os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
    os.execv(sys.executable, [sys.executable] + sys.argv)

from redis import Redis
from rq import Queue, SimpleWorker

from app.core.config import settings
from app.core.logging import logger


def main():
    logger.info("Starting RQ worker...")
    redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
    conn = Redis.from_url(redis_url)

    listen = [settings.RQ_QUEUE_NAME, "shadow_validation", "default"]
    queues = [Queue(name, connection=conn) for name in listen]
    # RQ's default Worker ends each forked workhorse with os._exit(), which skips
    # Python finalizers used by docling/PyTorch and leaks their semaphores. The
    # process is already dedicated to this queue, so execute jobs in-process and
    # allow normal cleanup instead of merely suppressing resource_tracker output.
    worker = SimpleWorker(queues, connection=conn)
    worker.work()


if __name__ == "__main__":
    main()
