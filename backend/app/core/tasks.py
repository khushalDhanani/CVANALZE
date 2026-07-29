import hashlib
import json
import logging
from typing import Any

from app.core.database import SessionLocal, pg_SessionLocal
from app.services.vacancy_service import VacancyService
from app.services.embedding_service import EmbeddingService
from app.models.pg import VacancyEmbedding
from sqlalchemy.dialects.postgresql import insert

logger = logging.getLogger(__name__)

def generate_canonical_text(job: dict[str, Any]) -> str:
    """
    Format locked in Phase 0:
    Title: {title}. Department: {department_name}. Description: {job_profile_description}. Required Skills: {required_skills_joined}. Preferred Keywords: {preferred_keywords_joined}.
    """
    title = job.get("title", "")
    dept = job.get("department_name") or job.get("department") or ""
    # In a real implementation we would fetch JobProfileDesc, but for now we fallback to empty if missing
    desc = job.get("description") or job.get("job_profile_description") or ""
    
    req_skills = job.get("required_skills", [])
    pref_keywords = job.get("preferred_keywords", [])
    
    req_skills_joined = ", ".join([str(s) for s in req_skills]) if req_skills else ""
    pref_keywords_joined = ", ".join([str(k) for k in pref_keywords]) if pref_keywords else ""

    text = f"Title: {title}. Department: {dept}. Description: {desc}. Required Skills: {req_skills_joined}. Preferred Keywords: {pref_keywords_joined}."
    return text

def embed_vacancy(vacancy_id: int) -> str:
    """
    RQ job to fetch a vacancy from MSSQL, compute its canonical text hash,
    and embed/upsert it into Postgres if it's new or changed.
    """
    if SessionLocal is None or pg_SessionLocal is None:
        return "Database not fully configured"

    mssql_db = SessionLocal()
    pg_db = pg_SessionLocal()
    try:
        service = VacancyService(mssql_db)
        
        # We need to fetch the specific vacancy
        # Wait, VacancyService doesn't have a get_vacancy_by_id currently.
        # We can just fetch all and filter, or add get_job_by_id to repository.
        from app.repositories.job import JobRepository
        job = JobRepository.get_job_by_id(str(vacancy_id), mssql_db)
        
        if not job:
            logger.warning(f"embed_vacancy: Vacancy {vacancy_id} not found in MSSQL or not active.")
            return f"Vacancy {vacancy_id} not found"

        canonical_text = generate_canonical_text(job)
        content_hash = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()

        # Check pg for existing content_hash
        existing = pg_db.query(VacancyEmbedding).filter(VacancyEmbedding.vacancy_id == vacancy_id).first()
        if existing and existing.content_hash == content_hash:
            logger.info(f"embed_vacancy: Vacancy {vacancy_id} unchanged. Skipping.")
            return "Skipped (unchanged)"

        # Generate embedding
        logger.info(f"embed_vacancy: Generating embedding for {vacancy_id}...")
        # Make sure to specify the right model
        from app.core.config import settings
        embedding = EmbeddingService.generate_embedding(canonical_text, settings.EMBEDDING_MODEL)
        
        if not embedding:
            logger.error(f"embed_vacancy: Failed to generate embedding for {vacancy_id}.")
            return "Failed to embed"

        # Upsert in pg
        stmt = insert(VacancyEmbedding).values(
            vacancy_id=vacancy_id,
            content_hash=content_hash,
            embedding=embedding
        )
        # On conflict do update
        stmt = stmt.on_conflict_do_update(
            index_elements=['vacancy_id'],
            set_={
                'content_hash': stmt.excluded.content_hash,
                'embedding': stmt.excluded.embedding,
                'updated_at': __import__('sqlalchemy').sql.func.now()
            }
        )
        pg_db.execute(stmt)
        pg_db.commit()
        logger.info(f"embed_vacancy: Successfully upserted {vacancy_id}.")
        return "Upserted"

    except Exception as exc:
        logger.error(f"embed_vacancy: Error processing {vacancy_id}: {exc}")
        pg_db.rollback()
        raise
    finally:
        mssql_db.close()
        pg_db.close()

def sync_all_vacancies() -> str:
    """
    Enqueues embed_vacancy for all active vacancies.
    """
    from redis import Redis
    from rq import Queue
    from app.core.config import settings
    from app.repositories.job import JobRepository
    
    redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
    conn = Redis.from_url(redis_url)
    q = Queue('default', connection=conn)

    mssql_db = SessionLocal()
    try:
        jobs = JobRepository.get_all_jobs(mssql_db)
        count = 0
        for job in jobs:
            vid = job.get("vacancy_id")
            if vid is not None:
                q.enqueue('app.core.tasks.embed_vacancy', int(vid))
                count += 1
        return f"Enqueued {count} vacancies for embedding sync."
    finally:
        mssql_db.close()
