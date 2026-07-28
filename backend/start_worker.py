import sys
import warnings
from redis import Redis
from rq import Worker, Queue

# Suppress harmless leaked semaphore warnings from docling/pytorch inside RQ workers
warnings.filterwarnings("ignore", category=UserWarning, module="multiprocessing.resource_tracker")

from app.core.config import settings
from app.core.logging import logger

def main():
    logger.info("Starting RQ worker...")
    redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
    conn = Redis.from_url(redis_url)

    listen = ['default']
    queues = [Queue(name, connection=conn) for name in listen]
    worker = Worker(queues, connection=conn)
    worker.work()

if __name__ == '__main__':
    main()
