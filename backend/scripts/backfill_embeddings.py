import os
import sys
import time

# Ensure backend directory is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from redis import Redis
from rq import Queue
from sqlalchemy import text

from app.core.config import settings
from app.core.database import pg_engine
from app.core.tasks import sync_all_vacancies


def main():
    start_time = time.time()
    
    print("1. Adding content_hash column if it does not exist...")
    if pg_engine is not None:
        with pg_engine.connect() as conn:
            conn.execute(text("ALTER TABLE vacancy_embeddings ADD COLUMN IF NOT EXISTS content_hash VARCHAR;"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vacancy_embeddings_content_hash ON vacancy_embeddings (content_hash);"))
            conn.commit()
    else:
        print("PG engine not initialized.")
        return

    print("2. Enqueueing sync for all active vacancies...")
    msg = sync_all_vacancies()
    print(msg)

    print("3. Waiting for RQ worker to finish jobs...")
    redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
    conn = Redis.from_url(redis_url)
    q = Queue('default', connection=conn)

    while True:
        job_count = len(q)
        if job_count == 0:
            # wait a bit to see if worker is finishing the last job
            time.sleep(2)
            if len(q) == 0:
                break
        print(f"Waiting... {job_count} jobs remaining in queue.")
        time.sleep(5)
        
    print("Queue is empty. Verifying count...")

    with pg_engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM vacancy_embeddings")).scalar()

    end_time = time.time()
    duration = end_time - start_time
    print(f"Gate: SELECT COUNT(*) FROM vacancy_embeddings = {result}")
    print(f"Backfill Runtime: {duration:.2f} seconds")

if __name__ == "__main__":
    main()
