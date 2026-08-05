import hashlib
import logging
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.core.database import pg_SessionLocal
from app.models.pg import VacancyEmbedding
from app.services.embedding_service import get_embedding

logger = logging.getLogger(__name__)


def generate_canonical_text(job: dict[str, Any]) -> str:
    """
    Locked format from Phase 0:
    Title: {title} | Department: {department} | Required Skills: {skills} | Preferred Keywords: {keywords} | Location: {location}
    Normalized to single-spaced lowercase text.
    """
    title = str(job.get("title", "") or "").strip()
    dept = str(job.get("department_name") or job.get("department") or "").strip()

    req_skills = job.get("required_skills", []) or []
    pref_keywords = job.get("preferred_keywords", []) or []

    req_skills_str = ", ".join([str(s).strip() for s in req_skills if str(s).strip()])
    pref_keywords_str = ", ".join([str(k).strip() for k in pref_keywords if str(k).strip()])
    location_str = str(job.get("location_name", "") or "").strip()

    parts = [
        f"Title: {title}",
        f"Department: {dept}",
        f"Required Skills: {req_skills_str}",
        f"Preferred Keywords: {pref_keywords_str}",
        f"Location: {location_str}",
    ]
    raw_text = " | ".join(parts)
    return " ".join(raw_text.split()).lower()


def embed_vacancy(vacancy_id: int | str, job_dict: dict[str, Any] | None = None) -> str:
    """
    RQ job / function to fetch a vacancy from MSSQL, compute its canonical text hash,
    and embed/upsert it into Postgres if it's new or changed.
    """
    if pg_SessionLocal is None:
        logger.error("embed_vacancy: pg_SessionLocal is None")
        return "PG DB not configured"

    vid_int = int(vacancy_id)
    if job_dict is None:
        from app.repositories.job import JobRepository

        job_dict = JobRepository.get_job_by_id(str(vid_int))

    if not job_dict:
        logger.warning(f"embed_vacancy: Vacancy {vacancy_id} not found.")
        return f"Vacancy {vacancy_id} not found"

    canonical_text = generate_canonical_text(job_dict)
    content_hash = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()

    pg_db = pg_SessionLocal()
    try:
        existing = pg_db.query(VacancyEmbedding).filter(VacancyEmbedding.vacancy_id == vid_int).first()
        if existing and existing.content_hash == content_hash and existing.embedding is not None:
            logger.info(f"embed_vacancy: Vacancy {vid_int} unchanged. Skipping.")
            return "Skipped (unchanged)"

        logger.info(f"embed_vacancy: Generating embedding for vacancy_id={vid_int}...")
        embedding = get_embedding(canonical_text, model_name=settings.EMBEDDING_MODEL)

        if not embedding:
            logger.error(f"embed_vacancy: Failed to generate embedding for vacancy_id={vid_int}.")
            return "Failed to embed"

        stmt = insert(VacancyEmbedding).values(
            vacancy_id=vid_int,
            embedding=embedding,
            embedding_model_version=settings.EMBEDDING_MODEL,
            content_hash=content_hash,
            updated_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["vacancy_id"],
            set_={
                "embedding": stmt.excluded.embedding,
                "embedding_model_version": stmt.excluded.embedding_model_version,
                "content_hash": stmt.excluded.content_hash,
                "updated_at": func.now(),
            },
        )
        pg_db.execute(stmt)
        pg_db.commit()
        logger.info(f"embed_vacancy: Successfully upserted vacancy_id={vid_int}.")
        return "Upserted"

    except Exception as exc:
        pg_db.rollback()
        logger.error(f"embed_vacancy: Error processing vacancy_id={vid_int}: {exc}")
        raise
    finally:
        pg_db.close()


def sync_all_vacancies() -> str:
    """
    Enqueue one bounded vacancy batch so Ollama is loaded and unloaded once.
    """
    from app.repositories.job import JobRepository

    jobs = JobRepository.get_all_jobs()
    valid_jobs = [job for job in jobs if str(job.get("vacancy_id") or job.get("id") or "").isdigit()]
    count = len(valid_jobs)

    try:
        from redis import Redis
        from rq import Queue

        redis_url = settings.REDIS_URL
        conn = Redis.from_url(redis_url)
        q = Queue(settings.RQ_QUEUE_NAME, connection=conn)
        q.enqueue("app.core.tasks.embed_vacancies_batch", valid_jobs)
        return f"Enqueued {count} vacancies for embedding sync."
    except Exception as exc:
        logger.warning(f"RQ queue sync failed, running synchronously: {exc}")
        embed_vacancies_batch(valid_jobs)
        return f"Synchronously processed {count} vacancies for embedding sync."


def embed_vacancies_batch(job_dicts: list[dict[str, Any]]) -> dict[str, int]:
    """RQ-compatible vacancy batch entry point using the centralized embedding service."""
    from app.services.embedding_sync_service import EmbeddingSyncService

    return EmbeddingSyncService.sync_vacancy_embeddings(job_dicts)
