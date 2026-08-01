import time

from sqlalchemy import text

from app.core.database import pg_engine
from app.core.tasks import embed_vacancy
from app.repositories.job import JobRepository


def run_backfill():
    print("Fetching active vacancies...")
    start_time = time.perf_counter()

    jobs = JobRepository.get_all_jobs()
    total_jobs = len(jobs)
    print(f"Loaded {total_jobs} active vacancies from repository.")

    upserted_count = 0
    skipped_count = 0
    failed_count = 0

    for idx, job in enumerate(jobs, 1):
        vid = job.get("vacancy_id") or job.get("id")
        if vid is None or not str(vid).isdigit():
            print(f"[{idx}/{total_jobs}] Skipping invalid vacancy_id: {vid}")
            continue

        try:
            res = embed_vacancy(int(vid), job_dict=job)
            if "Upserted" in res:
                upserted_count += 1
            elif "Skipped" in res:
                skipped_count += 1
            else:
                failed_count += 1
        except Exception as exc:
            print(f"[{idx}/{total_jobs}] Error embedding vacancy {vid}: {exc}")
            failed_count += 1

    end_time = time.perf_counter()
    duration = end_time - start_time

    # Query Postgres count
    with pg_engine.connect() as conn:
        pg_count = conn.execute(text("SELECT COUNT(*) FROM vacancy_embeddings")).scalar()

    print("\n" + "=" * 50)
    print("BACKFILL SUMMARY PROOF")
    print(f"Total Vacancies Processed: {total_jobs}")
    print(f"Upserted: {upserted_count}")
    print(f"Skipped (Unchanged): {skipped_count}")
    print(f"Failed: {failed_count}")
    print(f"PostgreSQL vacancy_embeddings COUNT(*): {pg_count}")
    print(f"Backfill Script Total Runtime: {duration:.2f} seconds ({duration / 60:.2f} minutes)")
    print("=" * 50)


if __name__ == "__main__":
    run_backfill()
