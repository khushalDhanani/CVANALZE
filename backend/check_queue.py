from redis import Redis
from rq import Queue
from rq.registry import FailedJobRegistry
from app.core.config import settings

conn = Redis.from_url(settings.REDIS_URL or "redis://localhost:6379/0")
q = Queue(settings.RQ_QUEUE_NAME, connection=conn)
print(f"Queue {q.name} length: {len(q)}")
failed_registry = FailedJobRegistry(queue=q)
print(f"Failed registry length: {len(failed_registry)}")
for job_id in failed_registry.get_job_ids():
    job = q.fetch_job(job_id)
    if job:
        print(f"Failed job: {job.id}, error: {job.exc_info[:100]}")
