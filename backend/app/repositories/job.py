from __future__ import annotations
# backend/app/repositories/job.py
import hashlib
import json
import threading
import time
from dataclasses import dataclass
from datetime import timezone
from enum import Enum
from typing import Any, ClassVar

from sqlalchemy.orm import Session

from app.core.cache import CacheInvalidator, vacancy_cache_manager
from app.core.database import MssqlReadSession

from app.core.logging import logger
from app.services.embedding_sync_service import EmbeddingSyncService
from app.services.job_preprocessor import JobPreprocessor
from app.services.vacancy_service import VacancyService

VACANCY_CACHE_KEY = "all_jobs"


class VacancyLoadStatus(str, Enum):
    SUCCESS = "success"
    EMPTY = "empty"
    STALE = "stale"


@dataclass(frozen=True)
class VacancyLoadResult:
    jobs: list[dict[str, Any]]
    status: VacancyLoadStatus


class VacancySourceUnavailableError(RuntimeError):
    """Raised when MSSQL cannot be read and no cached vacancy snapshot exists."""


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

            cls.last_loaded_timestamp = datetime.now(timezone.utc).isoformat()

    @classmethod
    def record_staleness_check(cls, duration_ms: float) -> None:
        with cls._lock:
            cls.staleness_check_count += 1
            cls.staleness_check_time_total_ms += duration_ms

    @classmethod
    def get_metrics(cls) -> dict[str, Any]:
        with cls._lock:
            avg_db_fetch_ms = round(cls.db_fetch_time_total_ms / cls.db_fetch_count, 2) if cls.db_fetch_count > 0 else 0.0
            avg_stale_ms = round(cls.staleness_check_time_total_ms / cls.staleness_check_count, 2) if cls.staleness_check_count > 0 else 0.0
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
    Queries live MSSQL DB vacancies and falls back only to the last successful cached snapshot.
    Uses CacheManager (Memory L1 + Redis L2) with version-aware caching.
    Business logic (taxonomy, embedding sync) is decoupled into dedicated services.
    """

    _VACANCY_CACHE_KEY = VACANCY_CACHE_KEY
    _VERSION_CACHE_KEY = "all_jobs_version"
    _STALENESS_CACHE: ClassVar[dict[str, tuple[float, bool]]] = {}
    _STALENESS_TTL = 30.0
    _VACANCY_EMBEDDINGS_CACHED = False

    @classmethod
    def invalidate_cache(cls) -> None:
        cls._STALENESS_CACHE.clear()
        CacheInvalidator.invalidate_vacancies()
        logger.info("JobRepository.invalidate_cache: Cache invalidated.")

    @classmethod
    def _compute_vacancy_hash(cls, job_dicts: list[dict[str, Any]]) -> str:
        return cls.compute_matching_vacancy_version(job_dicts)

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
        result = cls.load_all_jobs(db=db)
        if result.status == VacancyLoadStatus.STALE and not result.jobs:
            raise VacancySourceUnavailableError("MSSQL vacancy source is unavailable and the cached vacancy snapshot is empty.")
        return result.jobs

    @classmethod
    def load_all_jobs(cls, db: Session | None = None) -> VacancyLoadResult:
        cached_entry = vacancy_cache_manager.get(cls._VACANCY_CACHE_KEY)
        cached_jobs: list[dict[str, Any]] | None = None
        if cached_entry is not None:
            if isinstance(cached_entry, dict) and isinstance(cached_entry.get("jobs"), list) and "version" in cached_entry:
                stored_jobs = cached_entry["jobs"]
                stored_version = str(cached_entry["version"])
                cached_jobs = stored_jobs
                staleness = cls._is_stale(stored_version, stored_jobs, db)
                if staleness is False:
                    RepositoryMetrics.record_cache_hit()
                    logger.info("JobRepository.get_all_jobs: CACHE HIT. Returning cached vacancies.")
                    status = VacancyLoadStatus.SUCCESS if stored_jobs else VacancyLoadStatus.EMPTY
                    return VacancyLoadResult(jobs=stored_jobs, status=status)
                if staleness is None:
                    RepositoryMetrics.record_cache_hit()
                    logger.warning("JobRepository.get_all_jobs: MSSQL unavailable. Returning stale cached vacancies.")
                    return VacancyLoadResult(jobs=stored_jobs, status=VacancyLoadStatus.STALE)
                logger.info("JobRepository.get_all_jobs: Vacancy changes detected. Re-fetching.")
            else:
                cached_jobs = cached_entry if isinstance(cached_entry, list) else None
                logger.info("JobRepository.get_all_jobs: Legacy cache entry detected. Revalidating against MSSQL.")

        RepositoryMetrics.record_cache_miss()
        logger.info("JobRepository.get_all_jobs: CACHE MISS. Fetching from DB.")
        t0 = time.perf_counter()

        close_session = False
        if db is None and MssqlReadSession is not None:
            try:
                db = MssqlReadSession()
                close_session = True
            except Exception as exc:
                logger.warning(f"Could not create DB session: {exc}")
                db = None

        if db is None:
            if cached_jobs is not None:
                RepositoryMetrics.record_cache_hit()
                logger.warning("JobRepository.get_all_jobs: MSSQL session unavailable. Returning stale cached vacancies.")
                return VacancyLoadResult(jobs=cached_jobs, status=VacancyLoadStatus.STALE)
            raise VacancySourceUnavailableError("MSSQL vacancy source is unavailable.")

        try:
            service = VacancyService(db)
            vacancies = service.get_active_vacancies()
            raw_dicts = [vacancy.model_dump() for vacancy in vacancies]
            job_dicts_to_return = JobPreprocessor.preprocess_job_dicts(raw_dicts)
            unique_dept_ids = sorted(
                {department_id for job in job_dicts_to_return if (department_id := job.get("department_id")) is not None}
            )
            logger.info(
                f"JobRepository.get_all_jobs: Active Vacancies: {len(job_dicts_to_return)} | "
                f"Departments: {len(unique_dept_ids)} | Department IDs: {unique_dept_ids}"
            )
        except Exception as exc:
            logger.error(f"JobRepository.get_all_jobs error querying DB: {exc}")
            if cached_jobs is not None:
                RepositoryMetrics.record_cache_hit()
                logger.warning("JobRepository.get_all_jobs: Returning stale cached vacancies after MSSQL query failure.")
                return VacancyLoadResult(jobs=cached_jobs, status=VacancyLoadStatus.STALE)
            raise VacancySourceUnavailableError("MSSQL vacancy source is unavailable.") from exc
        finally:
            if close_session:
                db.close()

        version = cls._compute_vacancy_hash(job_dicts_to_return)
        vacancy_cache_manager.set(
            cls._VACANCY_CACHE_KEY,
            {"jobs": job_dicts_to_return, "version": version},
        )
        cls._STALENESS_CACHE[version] = (time.monotonic(), False)
        # Delegate embedding sync to EmbeddingSyncService in a background thread
        # so the HTTP response is returned immediately without blocking on Ollama calls.
        _sync_thread = threading.Thread(
            target=EmbeddingSyncService.sync_vacancy_embeddings,
            args=(list(job_dicts_to_return),),
            daemon=True,
            name="vacancy-embedding-sync",
        )
        _sync_thread.start()
        cls._VACANCY_EMBEDDINGS_CACHED = True

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        RepositoryMetrics.record_db_fetch(elapsed_ms, len(job_dicts_to_return), version)

        status = VacancyLoadStatus.SUCCESS if job_dicts_to_return else VacancyLoadStatus.EMPTY
        return VacancyLoadResult(jobs=job_dicts_to_return, status=status)

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
    ) -> bool | None:
        """
        Lightweight staleness check: checks if live DB vacancies (IDs, titles, count) differ from stored_version.
        Returns True if database vacancies changed, False if up to date, and None when MSSQL cannot be checked.
        """
        t0 = time.perf_counter()
        now = time.monotonic()
        if stored_version in cls._STALENESS_CACHE:
            cached_time, cached_result = cls._STALENESS_CACHE[stored_version]
            if now - cached_time < cls._STALENESS_TTL:
                return cached_result

        close_session = False
        if db is None and MssqlReadSession is not None:
            try:
                db = MssqlReadSession()
                close_session = True
            except Exception as exc:
                logger.warning(f"JobRepository._is_stale: Failed resolving DB session: {exc}")
                db = None

        if db is None:
            return None

        try:
            from sqlalchemy import or_, select
            from app.models.mssql.vacancy import RecruitVacancyRequest

            stmt = select(RecruitVacancyRequest.VacancyRequestID).where(
                RecruitVacancyRequest.VacancyRequestIsActive == True,
                or_(
                    RecruitVacancyRequest.VacancyRequestIsDeleted == False,
                    RecruitVacancyRequest.VacancyRequestIsDeleted.is_(None),
                ),
                or_(
                    RecruitVacancyRequest.VacancyRequestClose == False,
                    RecruitVacancyRequest.VacancyRequestClose.is_(None),
                ),
                or_(
                    RecruitVacancyRequest.VacancyRequestIsForceClosed == False,
                    RecruitVacancyRequest.VacancyRequestIsForceClosed.is_(None),
                ),
            ).order_by(RecruitVacancyRequest.VacancyRequestID)
            
            rows = db.execute(stmt).scalars().all()
            db_pairs = sorted(str(row) for row in rows)
            db_version = hashlib.sha256(json.dumps(db_pairs).encode()).hexdigest()
            stored_ids = sorted(str(job.get("vacancy_id") or job.get("id")) for job in stored_jobs)
            stored_ids_version = hashlib.sha256(json.dumps(stored_ids).encode()).hexdigest()
            is_stale_result = db_version != stored_ids_version
            if is_stale_result:
                logger.info(f"[STALENESS_DEBUG] db_count={len(db_pairs)} stored_count={len(stored_ids)} db_diff={set(db_pairs)-set(stored_ids)} stored_diff={set(stored_ids)-set(db_pairs)}")
            else:
                logger.info(f"[STALENESS_DEBUG] Staleness check matched! count={len(db_pairs)}")

            cls._STALENESS_CACHE[stored_version] = (now, is_stale_result)

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            RepositoryMetrics.record_staleness_check(elapsed_ms)
            return is_stale_result
        except Exception as exc:
            try:
                db.rollback()
                from sqlalchemy import func, or_

                from app.models.mssql.vacancy import RecruitVacancyRequest

                count = (
                    db.query(func.count(RecruitVacancyRequest.VacancyRequestID))
                    .filter(
                        RecruitVacancyRequest.VacancyRequestIsActive == True,
                        or_(
                            RecruitVacancyRequest.VacancyRequestIsDeleted == False,
                            RecruitVacancyRequest.VacancyRequestIsDeleted.is_(None),
                        ),
                        or_(
                            RecruitVacancyRequest.VacancyRequestClose == False,
                            RecruitVacancyRequest.VacancyRequestClose.is_(None),
                        ),
                        or_(
                            RecruitVacancyRequest.VacancyRequestIsForceClosed == False,
                            RecruitVacancyRequest.VacancyRequestIsForceClosed.is_(None),
                        ),
                    )
                    .scalar()
                    or 0
                )
                is_stale_result = count != len(stored_jobs)
                cls._STALENESS_CACHE[stored_version] = (now, is_stale_result)

                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                RepositoryMetrics.record_staleness_check(elapsed_ms)
                return is_stale_result
            except Exception as inner_exc:
                logger.warning(f"Staleness check failed: {exc} | fallback: {inner_exc}")
                return None
        finally:
            if close_session:
                db.close()

    @classmethod
    def get_job_by_id(cls, job_id: str, db: Session | None = None) -> dict[str, Any] | None:
        jobs = cls.get_all_jobs(db=db)
        return next(
            (job for job in jobs if str(job.get("id")) == str(job_id) or str(job.get("vacancy_id")) == str(job_id)),
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
