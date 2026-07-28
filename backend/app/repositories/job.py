import re
from typing import Any
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.jobs import DEFAULT_JOB_OPENINGS
from app.core.logging import logger
from app.services.vacancy_service import VacancyService


class JobRepository:
    """
    Repository for accessing Job Openings.
    Queries live MSSQL DB vacancies when available, with fallback to DEFAULT_JOB_OPENINGS.
    """
    
    _job_cache: list[dict[str, Any]] | None = None
    _cache_populated: bool = False

    @classmethod
    def invalidate_cache(cls) -> None:
        cls._job_cache = None
        cls._cache_populated = False
        logger.info("JobRepository.invalidate_cache: Cache cleared.")

    @classmethod
    def _precompute_job_fields(cls, job: dict[str, Any]) -> dict[str, Any]:
        """Precomputes and caches tokens used by VacancyPreFilter for fast evaluation."""
        stop_words = {"and", "team", "for", "the", "with", "senior", "junior", "lead", "manager", "developer", "engineer", "specialist"}
        
        # Precompute Department
        dept_name = (job.get("department_name") or job.get("department") or "").lower()
        job["_precomputed_dept"] = dept_name
        
        # Precompute Title Terms
        title = job.get("title", "").lower()
        title_terms = [
            t for t in re.split(r"[\s/&()\-,]+", title)
            if len(t) > 2 and t not in stop_words
        ]
        job["_precomputed_title_terms"] = title_terms
        
        # Precompute Required Skills
        req_skills = job.get("required_skills", [])
        job["_precomputed_req_skills"] = [s.lower() for s in req_skills if isinstance(s, str)]
        
        # Precompute Preferred Keywords
        pref_keywords = job.get("preferred_keywords", [])
        job["_precomputed_pref_keywords"] = [k.lower() for k in pref_keywords if isinstance(k, str)]
        
        return job

    @classmethod
    def get_all_jobs(cls, db: Session | None = None) -> list[dict[str, Any]]:
        if cls._cache_populated and cls._job_cache is not None:
            logger.info("JobRepository.get_all_jobs: CACHE HIT. Returning cached vacancies.")
            return cls._job_cache
            
        logger.info("JobRepository.get_all_jobs: CACHE MISS. Fetching from DB.")

        # If db session provided or SessionLocal is configured, fetch live DB vacancies
        close_session = False
        if db is None and SessionLocal is not None:
            try:
                db = SessionLocal()
                close_session = True
            except Exception as exc:
                logger.warning(f"Could not create DB session: {exc}")
                db = None

        job_dicts_to_return = None

        if db is not None:
            try:
                service = VacancyService(db)
                vacancies = service.get_active_vacancies()
                if vacancies:
                    job_dicts = [v.model_dump() for v in vacancies]
                    
                    # Precompute fields for caching
                    job_dicts = [cls._precompute_job_fields(j) for j in job_dicts]
                    
                    unique_dept_ids = sorted(list({j.get("department_id") for j in job_dicts if j.get("department_id") is not None}))
                    logger.info(
                        f"JobRepository.get_all_jobs: Active Vacancies: {len(job_dicts)} | Departments: {len(unique_dept_ids)} | Department IDs: {unique_dept_ids}"
                    )
                    job_dicts_to_return = job_dicts
                else:
                    logger.warning("JobRepository.get_all_jobs: 0 active vacancies returned from MSSQL DB. Falling back to default jobs.")
            except Exception as exc:
                logger.error(f"JobRepository.get_all_jobs error querying DB: {exc}")
                if settings.DB_NAME:
                    raise RuntimeError(f"Failed to query active vacancies from configured MSSQL DB: {exc}") from exc
            finally:
                if close_session:
                    db.close()

        if job_dicts_to_return is None:
            logger.warning("JobRepository.get_all_jobs: Using static DEFAULT_JOB_OPENINGS fallback.")
            job_dicts_to_return = [cls._precompute_job_fields(dict(j)) for j in DEFAULT_JOB_OPENINGS]
            
        cls._job_cache = job_dicts_to_return
        cls._cache_populated = True
        
        return cls._job_cache

    @classmethod
    def get_job_by_id(cls, job_id: str, db: Session | None = None) -> dict[str, Any] | None:
        jobs = cls.get_all_jobs(db=db)
        return next((job for job in jobs if str(job.get("id")) == str(job_id) or str(job.get("vacancy_id")) == str(job_id)), None)

