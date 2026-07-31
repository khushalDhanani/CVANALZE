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
from app.services.job_taxonomy import TaxonomyClassifier


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
    _STALENESS_CACHE: dict[str, tuple[float, bool]] = {}
    _STALENESS_TTL = 10.0

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
        """Precomputes and caches tokens & taxonomy used by VacancyPreFilter for fast evaluation."""
        stop_words = {
            "and", "team", "for", "the", "with",
            "senior", "junior", "lead", "manager",
            "specialist",
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

        # Populate Taxonomy Metadata
        domain, job_family = TaxonomyClassifier.classify_vacancy(job)
        job["domain"] = domain
        job["job_family"] = job_family
        job["_precomputed_domain"] = domain
        job["_precomputed_job_family"] = job_family

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
        Lightweight staleness check: resolves a DB session if db is None, and checks
        if live DB vacancies (IDs, titles, count) differ from stored_version/stored_jobs.
        Returns True if database vacancies changed, False if up to date.
        """
        import time
        now = time.monotonic()
        if stored_version in cls._STALENESS_CACHE:
            cached_time, cached_result = cls._STALENESS_CACHE[stored_version]
            if now - cached_time < cls._STALENESS_TTL:
                return cached_result

        close_session = False
        if db is None and SessionLocal is not None:
            try:
                db = SessionLocal()
                close_session = True
            except Exception as exc:
                logger.warning(f"JobRepository._is_stale: Failed resolving DB session: {exc}")
                db = None

        if db is None:
            return False

        try:
            from sqlalchemy import text
            query = text("""
                SELECT VacancyRequestID, ISNULL(VacancyRequestTitle, '')
                FROM RecruitVacancyRequest
                WHERE (VacancyRequestIsActive = 1 OR VacancyRequestIsActive IS NULL)
                  AND (VacancyRequestIsDeleted = 0 OR VacancyRequestIsDeleted IS NULL)
                  AND (VacancyRequestClose = 0 OR VacancyRequestClose IS NULL)
                ORDER BY VacancyRequestID
            """)
            rows = db.execute(query).fetchall()
            db_pairs = sorted(f"{r[0]}:{r[1]}" for r in rows)
            db_version = hashlib.sha256(json.dumps(db_pairs).encode()).hexdigest()

            is_stale_result = (db_version != stored_version) or (len(rows) != len(stored_jobs))
            cls._STALENESS_CACHE[stored_version] = (now, is_stale_result)
            return is_stale_result
        except Exception as exc:
            try:
                from sqlalchemy import func, or_
                from app.models.recruit import RecruitVacancyRequest
                count = db.query(func.count(RecruitVacancyRequest.VacancyRequestID)).filter(
                    RecruitVacancyRequest.VacancyRequestIsActive == True,
                    or_(RecruitVacancyRequest.VacancyRequestIsDeleted == False,
                        RecruitVacancyRequest.VacancyRequestIsDeleted.is_(None)),
                    or_(RecruitVacancyRequest.VacancyRequestClose == False,
                        RecruitVacancyRequest.VacancyRequestClose.is_(None)),
                ).scalar() or 0
                is_stale_result = count != len(stored_jobs)
                cls._STALENESS_CACHE[stored_version] = (now, is_stale_result)
                return is_stale_result
            except Exception as inner_exc:
                logger.warning(f"Staleness check failed: {exc} | fallback: {inner_exc}")
                cls._STALENESS_CACHE[stored_version] = (now, False)
                return False
        finally:
            if close_session:
                db.close()

    @classmethod
    def _cache_vacancy_embeddings(cls, job_dicts: list[dict[str, Any]]) -> None:
        """
        Generate and cache semantic vector embeddings for all active vacancies.
        Uses rich canonical text (Title, Description, Skills, Experience, Education, Certifications, Department, Responsibilities),
        checks content hashes for incremental updates, and persists embeddings to PostgreSQL and cache manager.
        """
        if not settings.EMBEDDING_ENABLED:
            return

        from app.core.cache import embedding_cache_manager as _ecm
        from app.services.embedding_service import (
            EmbeddingService as _es,
            build_vacancy_canonical_text,
            save_vacancy_embedding,
            get_vacancy_embedding,
        )

        model = settings.EMBEDDING_MODEL
        uncached: list[tuple[int, dict[str, Any], str, str]] = []  # (vac_id, job, canonical_text, content_hash)

        for job in job_dicts:
            vac_id = job.get("vacancy_id") or job.get("id")
            try:
                vac_id_int = int(vac_id) if vac_id is not None else 0
            except (ValueError, TypeError):
                vac_id_int = 0

            canonical_text = build_vacancy_canonical_text(job)
            if not canonical_text:
                continue

            content_hash = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()
            job["_canonical_text"] = canonical_text
            job["_content_hash"] = content_hash

            # Check if embedding already exists in cache or DB for this model and content hash
            cached_emb = _ecm.get(f"{model}:vac:{content_hash}")
            if cached_emb is None and vac_id_int > 0:
                pg_emb, stored_hash = get_vacancy_embedding(vac_id_int)
                if pg_emb is not None and stored_hash == content_hash:
                    cached_emb = pg_emb
                    _ecm.set(f"{model}:vac:{content_hash}", cached_emb)

            if cached_emb is None:
                uncached.append((vac_id_int, job, canonical_text, content_hash))

        if uncached:
            uncached_texts = [item[2] for item in uncached]
            embeddings = _es._call_ollama_batch_embed(model, uncached_texts)
            if embeddings is not None and len(embeddings) == len(uncached):
                for (vac_id_int, job, _, content_hash), emb in zip(uncached, embeddings):
                    if emb:
                        _ecm.set(f"{model}:vac:{content_hash}", emb)
                        if vac_id_int > 0:
                            save_vacancy_embedding(vac_id_int, emb, content_hash)

        cls._VACANCY_EMBEDDINGS_CACHED = True
        logger.info(
            f"[VACANCY_EMBEDDINGS] Processed {len(job_dicts)} vacancies: "
            f"{len(uncached)} newly embedded, {len(job_dicts) - len(uncached)} cached/unchanged."
        )

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
