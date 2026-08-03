# backend/app/repositories/job.py
import hashlib
import json
import threading
import time
from datetime import UTC
from typing import Any, ClassVar

from sqlalchemy.orm import Session

from app.core.cache import CacheInvalidator, vacancy_cache_manager
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.jobs import DEFAULT_JOB_OPENINGS
from app.core.logging import logger
from app.services.embedding_sync_service import EmbeddingSyncService
from app.services.job_preprocessor import JobPreprocessor
from app.services.vacancy_service import VacancyService

VACANCY_CACHE_KEY = "all_jobs"


class RepositoryMetrics:
    """Thread-safe telemetry metrics for JobRepository operations."""

    _lock = threading.RLock()
    cache_hits: int = 0
    cache_misses: int = 0
    db_fetch_count: int = 0
    db_fetch_time_total_ms: float = 0.0
    staleness_check_count: int = 0
    staleness_check_time_total_ms: float = 0.0
    total_jobs_loaded: int = 0
    last_version_hash: str = ""
    last_loaded_timestamp: str = ""

    @classmethod
    def record_cache_hit(cls) -> None:
        with cls._lock:
            cls.cache_hits += 1

    @classmethod
    def record_cache_miss(cls) -> None:
        with cls._lock:
            cls.cache_misses += 1

    @classmethod
    def record_db_fetch(cls, duration_ms: float, job_count: int, version: str) -> None:
        with cls._lock:
            cls.db_fetch_count += 1
            cls.db_fetch_time_total_ms += duration_ms
            cls.total_jobs_loaded = job_count
            cls.last_version_hash = version
            from datetime import datetime
            cls.last_loaded_timestamp = datetime.now(UTC).isoformat()

    @classmethod
    def record_staleness_check(cls, duration_ms: float) -> None:
        with cls._lock:
            cls.staleness_check_count += 1
            cls.staleness_check_time_total_ms += duration_ms

    @classmethod
    def get_metrics(cls) -> dict[str, Any]:
        with cls._lock:
            avg_db_fetch_ms = (
                round(cls.db_fetch_time_total_ms / cls.db_fetch_count, 2)
                if cls.db_fetch_count > 0
                else 0.0
            )
            avg_stale_ms = (
                round(cls.staleness_check_time_total_ms / cls.staleness_check_count, 2)
                if cls.staleness_check_count > 0
                else 0.0
            )
            return {
                "cache_hits": cls.cache_hits,
                "cache_misses": cls.cache_misses,
                "db_fetch_count": cls.db_fetch_count,
                "average_db_fetch_time_ms": avg_db_fetch_ms,
                "staleness_check_count": cls.staleness_check_count,
                "average_staleness_check_time_ms": avg_stale_ms,
                "total_jobs_loaded": cls.total_jobs_loaded,
                "last_version_hash": cls.last_version_hash,
                "last_loaded_timestamp": cls.last_loaded_timestamp,
            }


class JobRepository:
    """
    Enterprise Data Access Repository for Job Openings.
    Queries live MSSQL DB vacancies when available, with graceful fallback to DEFAULT_JOB_OPENINGS.
    Uses CacheManager (Memory L1 + Redis L2) with version-aware caching.
    Business logic (taxonomy, embedding sync) is decoupled into dedicated services.
    """

    _VACANCY_CACHE_KEY = VACANCY_CACHE_KEY
    _VERSION_CACHE_KEY = "all_jobs_version"
    _STALENESS_CACHE: ClassVar[dict[str, tuple[float, bool]]] = {}
    _STALENESS_TTL = 10.0
    _VACANCY_EMBEDDINGS_CACHED = False

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
    def compute_matching_vacancy_version(cls, job_dicts: list[dict[str, Any]]) -> str:
        """Hash the complete matching inputs so requirement changes isolate cached results."""
        ordered_jobs = sorted(
            job_dicts,
            key=lambda job: str(job.get("vacancy_id") or job.get("id") or ""),
        )
        canonical_payload = json.dumps(
            ordered_jobs,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

    @classmethod
    def get_all_jobs(cls, db: Session | None = None) -> list[dict[str, Any]]:
        cached_entry = vacancy_cache_manager.get(cls._VACANCY_CACHE_KEY)
        if cached_entry is not None:
            if isinstance(cached_entry, dict) and "jobs" in cached_entry and "version" in cached_entry:
                stored_jobs = cached_entry["jobs"]
                stored_version = cached_entry["version"]
                if not cls._is_stale(stored_version, stored_jobs, db):
                    RepositoryMetrics.record_cache_hit()
                    logger.info("JobRepository.get_all_jobs: CACHE HIT. Returning cached vacancies.")
                    return stored_jobs
                logger.info("JobRepository.get_all_jobs: Stale version detected. Re-fetching.")
            else:
                RepositoryMetrics.record_cache_hit()
                logger.info("JobRepository.get_all_jobs: CACHE HIT (legacy format). Returning cached vacancies.")
                return cached_entry

        RepositoryMetrics.record_cache_miss()
        logger.info("JobRepository.get_all_jobs: CACHE MISS. Fetching from DB.")
        t0 = time.perf_counter()

        close_session = False
        if db is None and SessionLocal is not None:
            try:
                db = SessionLocal()
                close_session = True
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Could not create DB session: {exc}")
                db = None

        job_dicts_to_return: list[dict[str, Any]] | None = None

        if db is not None:
            try:
                service = VacancyService(db)
                vacancies = service.get_active_vacancies()
                if vacancies:
                    raw_dicts = [v.model_dump() for v in vacancies]
                    # Delegate job preprocessing to JobPreprocessor
                    job_dicts = JobPreprocessor.preprocess_job_dicts(raw_dicts)

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
            job_dicts_to_return = JobPreprocessor.preprocess_job_dicts(
                [dict(j) for j in DEFAULT_JOB_OPENINGS]
            )

        version = cls._compute_vacancy_hash(job_dicts_to_return)
        vacancy_cache_manager.set(
            cls._VACANCY_CACHE_KEY,
            {"jobs": job_dicts_to_return, "version": version},
        )
        # Delegate embedding sync to EmbeddingSyncService
        EmbeddingSyncService.sync_vacancy_embeddings(job_dicts_to_return)
        cls._VACANCY_EMBEDDINGS_CACHED = True

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        RepositoryMetrics.record_db_fetch(elapsed_ms, len(job_dicts_to_return), version)

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
        Lightweight staleness check: checks if live DB vacancies (IDs, titles, count) differ from stored_version.
        Returns True if database vacancies changed, False if up to date.
        """
        t0 = time.perf_counter()
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
            except Exception as exc:  # noqa: BLE001
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
            if rows:
                db_pairs = sorted(f"{r[0]}:{r[1]}" for r in rows)
                db_version = hashlib.sha256(json.dumps(db_pairs).encode()).hexdigest()
                is_stale_result = db_version != stored_version
            else:
                is_stale_result = False

            cls._STALENESS_CACHE[stored_version] = (now, is_stale_result)

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            RepositoryMetrics.record_staleness_check(elapsed_ms)
            return is_stale_result
        except Exception as exc:  # noqa: BLE001
            try:
                db.rollback()
                from sqlalchemy import func, or_

                from app.models.recruit import RecruitVacancyRequest
                count = db.query(func.count(RecruitVacancyRequest.VacancyRequestID)).filter(
                    RecruitVacancyRequest.VacancyRequestIsActive == True,
                    or_(RecruitVacancyRequest.VacancyRequestIsDeleted == False,
                        RecruitVacancyRequest.VacancyRequestIsDeleted.is_(None)),
                    or_(RecruitVacancyRequest.VacancyRequestClose == False,
                        RecruitVacancyRequest.VacancyRequestClose.is_(None)),
                ).scalar() or 0
                is_stale_result = (count != len(stored_jobs)) if count > 0 else False
                cls._STALENESS_CACHE[stored_version] = (now, is_stale_result)

                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                RepositoryMetrics.record_staleness_check(elapsed_ms)
                return is_stale_result
            except Exception as inner_exc:  # noqa: BLE001
                logger.warning(f"Staleness check failed: {exc} | fallback: {inner_exc}")
                cls._STALENESS_CACHE[stored_version] = (now, False)
                return False
        finally:
            if close_session:
                db.close()

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

    @classmethod
    def get_metrics(cls) -> dict[str, Any]:
        """Exposes telemetry diagnostics and metrics for JobRepository operations."""
        return RepositoryMetrics.get_metrics()

    @classmethod
    def _cache_vacancy_embeddings(cls, jobs: list[dict[str, Any]]) -> dict[str, int]:
        """Compatibility wrapper returning batch vacancy-embedding sync metrics."""
        from app.services.embedding_sync_service import EmbeddingSyncService
        return EmbeddingSyncService.sync_vacancy_embeddings(jobs)
