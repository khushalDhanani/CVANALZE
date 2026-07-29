import hashlib
import json
import re
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.cache import CacheInvalidator, vacancy_cache_manager
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.jobs import DEFAULT_JOB_OPENINGS
from app.core.logging import logger
from app.services.embedding_service import EmbeddingService
from app.services.vacancy_service import VacancyService


VACANCY_CACHE_KEY = "all_jobs"


class JobRepository:
    """
    Repository for accessing Job Openings.
    Queries live MSSQL DB vacancies when available, with fallback to DEFAULT_JOB_OPENINGS.
    Uses CacheManager (Memory L1 + Redis L2) with version-aware caching:
    only re-fetches from DB when the underlying data actually changes.
    """

    _VACANCY_CACHE_KEY = VACANCY_CACHE_KEY
    _VERSION_CACHE_KEY = "all_jobs_version"

    @classmethod
    def invalidate_cache(cls) -> None:
        CacheInvalidator.invalidate_vacancies()
        logger.info("JobRepository.invalidate_cache: Cache invalidated.")

    @classmethod
    def _compute_vacancy_hash(cls, job_dicts: list[dict[str, Any]]) -> str:
        identity_pairs = sorted(
            f"{j.get('vacancy_id') or j.get('id')}:{j.get('title', '')}"
            for j in job_dicts
        )
        return hashlib.sha256(json.dumps(identity_pairs).encode()).hexdigest()

    @classmethod
    def _precompute_job_fields(cls, job: dict[str, Any]) -> dict[str, Any]:
        """Precomputes and caches tokens used by VacancyPreFilter for fast evaluation."""
        stop_words = {
            "and", "team", "for", "the", "with",
            "senior", "junior", "lead", "manager",
            "developer", "engineer", "specialist",
        }

        dept_name = (job.get("department_name") or job.get("department") or "").lower()
        job["_precomputed_dept"] = dept_name

        title = job.get("title", "").lower()
        title_terms = [
            t for t in re.split(r"[\s/&()\-,]+", title)
            if len(t) > 2 and t not in stop_words
        ]
        job["_precomputed_title_terms"] = title_terms

        req_skills = job.get("required_skills", [])
        job["_precomputed_req_skills"] = [s.lower() for s in req_skills if isinstance(s, str)]

        pref_keywords = job.get("preferred_keywords", [])
        job["_precomputed_pref_keywords"] = [
            k.lower() for k in pref_keywords if isinstance(k, str)
        ]

        return job

    @classmethod
    def get_all_jobs(cls, db: Session | None = None) -> list[dict[str, Any]]:
        cached_entry = vacancy_cache_manager.get(cls._VACANCY_CACHE_KEY)
        if cached_entry is not None:
            if isinstance(cached_entry, dict) and "jobs" in cached_entry and "version" in cached_entry:
                stored_jobs = cached_entry["jobs"]
                stored_version = cached_entry["version"]
                if not cls._is_stale(stored_version, stored_jobs, db):
                    logger.info("JobRepository.get_all_jobs: CACHE HIT. Returning cached vacancies.")
                    return stored_jobs
                logger.info("JobRepository.get_all_jobs: Stale version detected. Re-fetching.")
            else:
                logger.info("JobRepository.get_all_jobs: CACHE HIT (legacy format). Returning cached vacancies.")
                return cached_entry

        logger.info("JobRepository.get_all_jobs: CACHE MISS. Fetching from DB.")

        close_session = False
        if db is None and SessionLocal is not None:
            try:
                db = SessionLocal()
                close_session = True
            except Exception as exc:
                logger.warning(f"Could not create DB session: {exc}")
                db = None

        job_dicts_to_return: list[dict[str, Any]] | None = None

        if db is not None:
            try:
                service = VacancyService(db)
                vacancies = service.get_active_vacancies()
                if vacancies:
                    job_dicts = [v.model_dump() for v in vacancies]
                    job_dicts = [cls._precompute_job_fields(j) for j in job_dicts]

                    unique_dept_ids = sorted(
                        {
                            j.get("department_id")
                            for j in job_dicts
                            if j.get("department_id") is not None
                        }
                    )
                    logger.info(
                        f"JobRepository.get_all_jobs: Active Vacancies: {len(job_dicts)} | "
                        f"Departments: {len(unique_dept_ids)} | Department IDs: {unique_dept_ids}"
                    )
                    job_dicts_to_return = job_dicts
                else:
                    logger.warning(
                        "JobRepository.get_all_jobs: 0 active vacancies returned from MSSQL DB. "
                        "Falling back to default jobs."
                    )
            except Exception as exc:
                logger.error(f"JobRepository.get_all_jobs error querying DB: {exc}")
                if settings.DB_NAME:
                    raise RuntimeError(
                        f"Failed to query active vacancies from configured MSSQL DB: {exc}"
                    ) from exc
            finally:
                if close_session:
                    db.close()

        if job_dicts_to_return is None:
            logger.warning("JobRepository.get_all_jobs: Using static DEFAULT_JOB_OPENINGS fallback.")
            job_dicts_to_return = [
                cls._precompute_job_fields(dict(j)) for j in DEFAULT_JOB_OPENINGS
            ]

        version = cls._compute_vacancy_hash(job_dicts_to_return)
        vacancy_cache_manager.set(
            cls._VACANCY_CACHE_KEY,
            {"jobs": job_dicts_to_return, "version": version},
        )
        cls._cache_vacancy_embeddings(job_dicts_to_return)
        return job_dicts_to_return

    @classmethod
    def get_vacancy_version(cls) -> str:
        """Return the current vacancy version hash, or empty string if not cached."""
        cached = vacancy_cache_manager.get(cls._VACANCY_CACHE_KEY)
        if isinstance(cached, dict) and "version" in cached:
            return cached["version"]
        return ""

    @classmethod
    def _is_stale(
        cls,
        stored_version: str,
        stored_jobs: list[dict[str, Any]],
        db: Session | None = None,
    ) -> bool:
        """
        Lightweight staleness check: computes the hash of the currently cached
        vacancy identities (ID + title) and compares it against the stored version.
        This avoids a DB round-trip by re-hashing what we already have in memory.
        If the hash matches, the data has not changed.
        """
        current_hash = cls._compute_vacancy_hash(stored_jobs)
        return current_hash != stored_version

    @classmethod
    def _cache_vacancy_embeddings(cls, job_dicts: list[dict[str, Any]]) -> None:
        """Generate and cache embeddings for vacancies with ``vac:`` prefix for selective invalidation."""
        from app.core.cache import embedding_cache_manager as _ecm
        from app.services.embedding_service import EmbeddingService as _es

        texts: list[str] = []
        for job in job_dicts:
            title = job.get("title", "")
            dept = job.get("department_name") or job.get("department") or ""
            skills = " ".join(job.get("required_skills", []) or [])
            text = f"{title} {dept} {skills}".strip()
            if text:
                texts.append(text)

        if not texts:
            return

        model = settings.EMBEDDING_MODEL
        text_hashes = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts]
        uncached_indices = [
            i for i, h in enumerate(text_hashes)
            if _ecm.get(f"{model}:vac:{h}") is None
        ]

        if uncached_indices:
            uncached_texts = [texts[i] for i in uncached_indices]
            embeddings = _es._call_ollama_batch_embed(model, uncached_texts)
            if embeddings is not None and len(embeddings) == len(uncached_indices):
                for i, idx in enumerate(uncached_indices):
                    _ecm.set(f"{model}:vac:{text_hashes[idx]}", embeddings[i])

        cls._VACANCY_EMBEDDINGS_CACHED = True
        logger.info(f"[EMBED] Cached {len(texts)} vacancy embeddings.")

    _VACANCY_EMBEDDINGS_CACHED = False

    @classmethod
    def get_job_by_id(
        cls, job_id: str, db: Session | None = None
    ) -> dict[str, Any] | None:
        jobs = cls.get_all_jobs(db=db)
        return next(
            (
                job
                for job in jobs
                if str(job.get("id")) == str(job_id)
                or str(job.get("vacancy_id")) == str(job_id)
            ),
            None,
        )
