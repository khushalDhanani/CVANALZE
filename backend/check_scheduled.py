from redis import Redis
from rq import Queue
from rq.registry import ScheduledJobRegistry
from app.core.config import settings
import time

conn = Redis.from_url(settings.REDIS_URL or "redis://localhost:6379/0")
q = Queue(settings.RQ_QUEUE_NAME, connection=conn)
scheduled_registry = ScheduledJobRegistry(queue=q)
print(f"Scheduled registry length: {len(scheduled_registry)}")
for job_id in scheduled_registry.get_job_ids():
    job = q.fetch_job(job_id)
    if job:
        print(f"Scheduled job: {job.id}")
