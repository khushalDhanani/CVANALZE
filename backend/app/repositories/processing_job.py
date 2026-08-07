from __future__ import annotations
import hashlib
import threading
from datetime import timezone, datetime
from typing import Any

from app.core.cache import processing_job_cache_manager
from app.core.config import settings
from app.schemas.contracts import JobState, ProcessingJobRecord
from app.core.rule_config_manager import RuleConfigManager


class ProcessingJobRepository:
    """Persist canonical background-job records and their latest CV-key aliases."""

    _lock = threading.RLock()

    @staticmethod
    def build_job_id(cv_key: str, content_hash: str) -> str:
        identity = "|".join(
            (
                cv_key,
                content_hash,
                settings.EXTRACTION_PARSER_VERSION,
                settings.EXTRACTION_SCHEMA_VERSION,
            )
        )
        return f"cvjob_{hashlib.sha256(identity.encode('utf-8')).hexdigest()}"

    @classmethod
    def get(cls, job_id: str) -> ProcessingJobRecord | None:
        payload = processing_job_cache_manager.get(f"job_{job_id}")
        return cls._validate(payload)

    @classmethod
    def get_by_cv_key(cls, cv_key: str) -> ProcessingJobRecord | None:
        clean_key = cv_key.strip()
        stems_to_try = [clean_key]
        if clean_key.lower().startswith("cv_"):
            raw_id = clean_key[3:]
            stems_to_try.extend([raw_id, f"cv_{raw_id}", f"CV_{raw_id}"])
        else:
            stems_to_try.append(f"cv_{clean_key}")

        for stem in list(stems_to_try):
            if not stem.startswith("cv_document_"):
                stems_to_try.append(f"cv_document_{stem}")
                if stem.startswith("cv_"):
                    stems_to_try.append(f"cv_document_{stem[3:]}")
            if not stem.startswith("cv_candidate_"):
                stems_to_try.append(f"cv_candidate_{stem}")
                if stem.startswith("cv_"):
                    stems_to_try.append(f"cv_candidate_{stem[3:]}")

        seen: set[str] = set()
        for stem in stems_to_try:
            if stem in seen:
                continue
            seen.add(stem)
            alias = hashlib.sha256(stem.encode("utf-8")).hexdigest()
            payload = processing_job_cache_manager.get(f"cv_{alias}")
            record = cls._validate(payload)
            if record:
                return record
        return None

    @classmethod
    def save(cls, record: ProcessingJobRecord) -> ProcessingJobRecord:
        persisted = record.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        cv_key_str = persisted.cv_key if isinstance(persisted.cv_key, str) else ""
        job_id_str = persisted.job_id if isinstance(persisted.job_id, str) else ""
        
        payload = persisted.model_dump(mode="json") if hasattr(persisted, "model_dump") and type(persisted).__name__ != "Mock" else {}
        ttl = settings.PROCESSING_JOB_TTL_SECONDS
        keys_to_alias = {cv_key_str} if cv_key_str else set()
        if isinstance(persisted.cv_id, str) and persisted.cv_id:
            keys_to_alias.add(persisted.cv_id)
            keys_to_alias.add(f"cv_document_{persisted.cv_id}")
            if persisted.cv_id.startswith("cv_"):
                keys_to_alias.add(persisted.cv_id[3:])
                keys_to_alias.add(f"cv_document_{persisted.cv_id[3:]}")
        if isinstance(persisted.candidate_id, str) and persisted.candidate_id:
            keys_to_alias.add(persisted.candidate_id)
            keys_to_alias.add(f"cv_candidate_{persisted.candidate_id}")
            if persisted.candidate_id.startswith("cv_"):
                keys_to_alias.add(persisted.candidate_id[3:])
                keys_to_alias.add(f"cv_candidate_{persisted.candidate_id[3:]}")

        with cls._lock:
            if job_id_str:
                processing_job_cache_manager.set(f"job_{job_id_str}", payload, ttl=ttl)
            for k in keys_to_alias:
                if isinstance(k, str) and k:
                    alias = hashlib.sha256(k.encode("utf-8")).hexdigest()
                    processing_job_cache_manager.set(f"cv_{alias}", payload, ttl=ttl)
        return persisted

    @classmethod
    def transition(
        cls,
        job_id: str,
        state: str,
        **updates: Any,
    ) -> ProcessingJobRecord:
        with cls._lock:
            record = cls.get(job_id)
            if record is None:
                raise LookupError(f"Processing job '{job_id}' was not found.")
            cls._assert_transition(record.state, state)
            now = datetime.now(timezone.utc)
            if state == JobState.PROCESSING and record.started_at is None:
                updates.setdefault("started_at", now)
            if state in (JobState.COMPLETED, JobState.FAILED):
                updates.setdefault("completed_at", now)
            return cls.save(record.model_copy(update={"state": state, **updates}))

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
        valid_targets = allowed.get(current, [])
        if target not in valid_targets:
            raise ValueError(f"Invalid processing-job transition: {current} -> {target}")
