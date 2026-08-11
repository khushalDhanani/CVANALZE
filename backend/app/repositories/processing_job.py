from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, NoReturn

from sqlalchemy import or_

from app.core.cache import _REDIS_CLIENT, processing_job_cache_manager
from app.core.config import settings
from app.core.database import PostgresAppSession
from app.core.logging import logger
from app.core.rule_config_manager import RuleConfigManager
from app.models.processing_job import CVProcessingJob
from app.schemas.contracts import JobState, ProcessingExecutionMode, ProcessingJobRecord


class ProcessingJobPersistenceError(RuntimeError):
    """Raised when the authoritative PostgreSQL job ledger is unavailable."""


class ProcessingJobRepository:
    """Persist canonical CV job state in PostgreSQL and mirror point lookups to cache."""

    ACTIVE_STATES = (JobState.QUEUED, JobState.PROCESSING, JobState.RETRYING)
    _legacy_backfill_attempted = False

    @staticmethod
    def build_job_id(cv_key: str, content_hash: str) -> str:
        identity = "|".join((cv_key, content_hash, settings.EXTRACTION_PARSER_VERSION, settings.EXTRACTION_SCHEMA_VERSION))
        return f"cvjob_{hashlib.sha256(identity.encode('utf-8')).hexdigest()}"

    @classmethod
    def get(cls, job_id: str) -> ProcessingJobRecord | None:
        if PostgresAppSession is not None:
            try:
                with PostgresAppSession() as session:
                    row = session.get(CVProcessingJob, job_id)
                    if row is not None:
                        record = cls._from_row(row)
                        cls._save_cache(record)
                        return record
            except Exception as exc:
                cls._raise_database_error("read", exc)
        return cls._validate(processing_job_cache_manager.get(f"job_{job_id}"))

    @classmethod
    def get_by_cv_key(cls, cv_key: str) -> ProcessingJobRecord | None:
        keys = cls._identity_keys(cv_key)
        if PostgresAppSession is not None:
            try:
                with PostgresAppSession() as session:
                    row = (
                        session.query(CVProcessingJob)
                        .filter(
                            or_(
                                CVProcessingJob.cv_key.in_(keys),
                                CVProcessingJob.cv_id.in_(keys),
                                CVProcessingJob.candidate_id.in_(keys),
                            )
                        )
                        .order_by(CVProcessingJob.enqueue_sequence.desc())
                        .first()
                    )
                    if row is not None:
                        record = cls._from_row(row)
                        cls._save_cache(record)
                        return record
            except Exception as exc:
                cls._raise_database_error("read by CV key", exc)

        for key in keys:
            alias = hashlib.sha256(key.encode("utf-8")).hexdigest()
            record = cls._validate(processing_job_cache_manager.get(f"cv_{alias}"))
            if record:
                return record
        return None

    @classmethod
    def list_recent(cls, *, updated_since: datetime, limit: int) -> list[ProcessingJobRecord]:
        cls.backfill_legacy_cache()
        if PostgresAppSession is None:
            return []
        try:
            with PostgresAppSession() as session:
                active_rows = (
                    session.query(CVProcessingJob)
                    .filter(CVProcessingJob.state.in_(cls.ACTIVE_STATES))
                    .order_by(CVProcessingJob.enqueue_sequence.asc())
                    .all()
                )
                terminal_limit = max(0, limit - len(active_rows))
                terminal_rows = []
                if terminal_limit:
                    terminal_rows = (
                        session.query(CVProcessingJob)
                        .filter(
                            CVProcessingJob.state.notin_(cls.ACTIVE_STATES),
                            CVProcessingJob.updated_at >= updated_since,
                        )
                        .order_by(CVProcessingJob.updated_at.desc())
                        .limit(terminal_limit)
                        .all()
                    )
                rows = active_rows + terminal_rows
                return [cls._from_row(row) for row in rows]
        except Exception as exc:
            cls._raise_database_error("list", exc)

    @classmethod
    def list_active(cls, *, limit: int | None = None) -> list[ProcessingJobRecord]:
        cls.backfill_legacy_cache()
        if PostgresAppSession is None:
            return []
        try:
            with PostgresAppSession() as session:
                query = (
                    session.query(CVProcessingJob)
                    .filter(CVProcessingJob.state.in_(cls.ACTIVE_STATES))
                    .order_by(CVProcessingJob.enqueue_sequence.asc())
                )
                if limit is not None:
                    query = query.limit(limit)
                return [cls._from_row(row) for row in query.all()]
        except Exception as exc:
            cls._raise_database_error("list active", exc)

    @classmethod
    def count_active(cls) -> int:
        if PostgresAppSession is None:
            return 0
        try:
            with PostgresAppSession() as session:
                return session.query(CVProcessingJob).filter(CVProcessingJob.state.in_(cls.ACTIVE_STATES)).count()
        except Exception as exc:
            cls._raise_database_error("count active", exc)

    @classmethod
    def backfill_legacy_cache(cls) -> int:
        """Import pre-ledger Redis job records once so in-flight deployments remain observable."""
        if cls._legacy_backfill_attempted or PostgresAppSession is None:
            return 0
        imported = 0
        try:
            max_records = settings.CV_QUEUE_MAX_SIZE + settings.CV_JOB_LIST_LIMIT
            legacy_records: list[ProcessingJobRecord] = []
            logical_keys: set[str] = set()
            if _REDIS_CLIENT is not None:
                for redis_key in _REDIS_CLIENT.scan_iter(match="processing_job:job_*", count=100):
                    decoded = redis_key.decode("utf-8") if isinstance(redis_key, bytes) else str(redis_key)
                    logical_keys.add(decoded.removeprefix("processing_job:"))
            file_cache_dir = settings.UPLOADS_DIR / ".processing_jobs"
            if file_cache_dir.exists():
                logical_keys.update(path.stem for path in file_cache_dir.glob("job_*.json"))
            for logical_key in logical_keys:
                if len(legacy_records) >= max_records:
                    break
                record = cls._validate(processing_job_cache_manager.get(logical_key))
                if record is not None:
                    legacy_records.append(record)
            for record in sorted(legacy_records, key=lambda item: (item.created_at, item.job_id)):
                with PostgresAppSession() as session:
                    exists = session.get(CVProcessingJob, record.job_id) is not None
                if not exists:
                    cls.save(record)
                    imported += 1
            cls._legacy_backfill_attempted = True
            if imported:
                logger.info("Imported %s legacy CV processing job record(s) into PostgreSQL.", imported)
            return imported
        except Exception as exc:
            cls._raise_database_error("legacy backfill", exc)

    @classmethod
    def save(cls, record: ProcessingJobRecord) -> ProcessingJobRecord:
        now = datetime.now(timezone.utc)
        persisted = record.model_copy(update={"updated_at": now})
        if PostgresAppSession is not None:
            try:
                with PostgresAppSession.begin() as session:
                    row = session.get(CVProcessingJob, persisted.job_id, with_for_update=True)
                    if row is None:
                        row = CVProcessingJob(job_id=persisted.job_id)
                        session.add(row)
                    else:
                        persisted = persisted.model_copy(update={"version": row.version + 1})
                    cls._write_row(row, persisted)
                    session.flush()
                    persisted = cls._from_row(row)
            except Exception as exc:
                cls._raise_database_error("write", exc)
        cls._save_cache(persisted)
        return persisted

    @classmethod
    def transition(cls, job_id: str, state: str, **updates: Any) -> ProcessingJobRecord:
        if PostgresAppSession is not None:
            try:
                with PostgresAppSession.begin() as session:
                    row = session.get(CVProcessingJob, job_id, with_for_update=True)
                    if row is None:
                        raise LookupError(f"Processing job '{job_id}' was not found.")
                    current = cls._from_row(row)
                    cls._assert_transition(current.state, state)
                    transitioned = cls._transitioned(current, state, updates).model_copy(update={"version": row.version + 1})
                    cls._write_row(row, transitioned)
                    session.flush()
                    persisted = cls._from_row(row)
                cls._save_cache(persisted)
                return persisted
            except (LookupError, ValueError):
                raise
            except Exception as exc:
                cls._raise_database_error("transition", exc)

        record = cls.get(job_id)
        if record is None:
            raise LookupError(f"Processing job '{job_id}' was not found.")
        cls._assert_transition(record.state, state)
        return cls.save(cls._transitioned(record, state, updates))

    @classmethod
    def _transitioned(cls, record: ProcessingJobRecord, state: str, updates: dict[str, Any]) -> ProcessingJobRecord:
        now = datetime.now(timezone.utc)
        values = dict(updates)
        values["updated_at"] = now
        if state == JobState.PROCESSING:
            values.setdefault("started_at", record.started_at or now)
            values.setdefault("heartbeat_at", now)
        if state in (JobState.COMPLETED, JobState.COMPLETED_DEGRADED, JobState.FAILED, JobState.CANCELLED):
            values.setdefault("completed_at", now)
        return record.model_copy(update={"state": state, **values})

    @staticmethod
    def _write_row(row: CVProcessingJob, record: ProcessingJobRecord) -> None:
        data = record.model_dump(mode="python")
        data["execution_mode"] = record.execution_mode.value
        data["outcome"] = record.outcome.value if record.outcome else None
        data["error"] = record.error.model_dump(mode="json") if record.error else None
        data.pop("enqueue_sequence", None)
        for field, value in data.items():
            if hasattr(row, field):
                setattr(row, field, value)

    @staticmethod
    def _from_row(row: CVProcessingJob) -> ProcessingJobRecord:
        return ProcessingJobRecord.model_validate(
            {
                "job_id": row.job_id,
                "enqueue_sequence": row.enqueue_sequence,
                "cv_key": row.cv_key,
                "content_hash": row.content_hash,
                "filename": row.filename,
                "storage_filename": row.storage_filename,
                "content_type": row.content_type,
                "candidate_id": row.candidate_id,
                "source_candidate_id": row.source_candidate_id,
                "cv_id": row.cv_id,
                "parser_version": row.parser_version,
                "schema_version": row.schema_version,
                "state": row.state,
                "progress": row.progress,
                "stage": row.stage,
                "message": row.message,
                "execution_mode": row.execution_mode,
                "rq_job_id": row.rq_job_id,
                "attempt": row.attempt,
                "max_attempts": row.max_attempts,
                "enqueue_count": row.enqueue_count,
                "force_reprocess": row.force_reprocess,
                "outcome": row.outcome,
                "error": row.error,
                "version": row.version,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "started_at": row.started_at,
                "heartbeat_at": row.heartbeat_at,
                "completed_at": row.completed_at,
            }
        )

    @classmethod
    def _save_cache(cls, record: ProcessingJobRecord) -> None:
        payload = record.model_dump(mode="json")
        ttl = settings.PROCESSING_JOB_TTL_SECONDS
        processing_job_cache_manager.set(f"job_{record.job_id}", payload, ttl=ttl)
        for key in cls._identity_keys(record.cv_key, record.cv_id, record.candidate_id):
            alias = hashlib.sha256(key.encode("utf-8")).hexdigest()
            processing_job_cache_manager.set(f"cv_{alias}", payload, ttl=ttl)

    @staticmethod
    def _identity_keys(*values: str | None) -> set[str]:
        keys: set[str] = set()
        for value in values:
            clean = str(value or "").strip()
            if not clean:
                continue
            keys.add(clean)
            raw = clean[3:] if clean.lower().startswith("cv_") else clean
            keys.update({raw, f"cv_{raw}", f"CV_{raw}", f"cv_document_{raw}", f"cv_candidate_{raw}"})
            if not clean.startswith("cv_document_"):
                keys.add(f"cv_document_{clean}")
            if not clean.startswith("cv_candidate_"):
                keys.add(f"cv_candidate_{clean}")
        return keys

    @staticmethod
    def _validate(payload: Any) -> ProcessingJobRecord | None:
        if not isinstance(payload, dict):
            return None
        try:
            return ProcessingJobRecord.model_validate(payload)
        except Exception:
            return None

    @staticmethod
    def _assert_transition(current: str, target: str) -> None:
        allowed = RuleConfigManager.get_config().workflow.job_state_transitions
        if target not in allowed.get(current, []):
            raise ValueError(f"Invalid processing-job transition: {current} -> {target}")

    @staticmethod
    def _raise_database_error(operation: str, exc: Exception) -> NoReturn:
        logger.exception("PostgreSQL processing-job ledger %s failed: %s", operation, type(exc).__name__)
        raise ProcessingJobPersistenceError("The durable CV job ledger is temporarily unavailable.") from exc
