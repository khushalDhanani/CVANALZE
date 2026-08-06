from redis import Redis
from rq import Queue
from rq.registry import ScheduledJobRegistry
from app.core.config import settings
import datetime

conn = Redis.from_url(settings.REDIS_URL or "redis://localhost:6379/0")
q = Queue(settings.RQ_QUEUE_NAME, connection=conn)
scheduled = ScheduledJobRegistry(queue=q)
job_ids = scheduled.get_job_ids()
print(f"Requeueing {len(job_ids)} jobs from scheduled registry...")

for job_id in job_ids:
    scheduled.remove(job_id)
    job = q.fetch_job(job_id)
    if job:
        job.set_status('queued')
        q.enqueue_job(job)
        print(f"Requeued {job_id}")
