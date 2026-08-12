from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.core.database import PostgresAppBase

class SyncRun(PostgresAppBase):
    __tablename__ = "sync_runs"
    __table_args__ = {"schema": "integration"}

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False) # e.g. RUNNING, COMPLETED, FAILED
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    records_read = Column(Integer, default=0, nullable=False)
    records_inserted = Column(Integer, default=0, nullable=False)
    records_updated = Column(Integer, default=0, nullable=False)
    records_skipped = Column(Integer, default=0, nullable=False)
    records_failed = Column(Integer, default=0, nullable=False)
    watermark_before = Column(DateTime(timezone=True), nullable=True)
    watermark_after = Column(DateTime(timezone=True), nullable=True)

class SyncWatermark(PostgresAppBase):
    __tablename__ = "sync_watermarks"
    __table_args__ = {"schema": "integration"}

    entity_type = Column(String(50), primary_key=True)
    last_source_updated_at = Column(DateTime(timezone=True), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class SyncError(PostgresAppBase):
    __tablename__ = "sync_errors"
    __table_args__ = {"schema": "integration"}

    id = Column(BigInteger, primary_key=True, index=True)
    sync_run_id = Column(Integer, ForeignKey("integration.sync_runs.id"), nullable=False)
    entity_type = Column(String(50), nullable=False)
    source_id = Column(String(100), nullable=False)
    error_type = Column(String(100), nullable=False)
    error_message = Column(String, nullable=False) # Without PII
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_resolved = Column(Boolean, default=False, nullable=False)

class DepartmentSnapshot(PostgresAppBase):
    __tablename__ = "department_snapshots"
    __table_args__ = (
        Index("ix_department_snapshots_is_active", "is_active"),
        {"schema": "integration"}
    )

    source_id = Column(String(100), primary_key=True)
    source_hash = Column(String(64), nullable=False)
    source_updated_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    payload = Column(JSONB, nullable=False)

class DesignationSnapshot(PostgresAppBase):
    __tablename__ = "designation_snapshots"
    __table_args__ = (
        Index("ix_designation_snapshots_is_active", "is_active"),
        {"schema": "integration"}
    )

    source_id = Column(String(100), primary_key=True)
    source_hash = Column(String(64), nullable=False)
    source_updated_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    payload = Column(JSONB, nullable=False)

class JobProfileSnapshot(PostgresAppBase):
    __tablename__ = "job_profile_snapshots"
    __table_args__ = (
        Index("ix_job_profile_snapshots_is_active", "is_active"),
        {"schema": "integration"}
    )

    source_id = Column(String(100), primary_key=True)
    source_hash = Column(String(64), nullable=False)
    source_updated_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    payload = Column(JSONB, nullable=False)

class CandidateSnapshot(PostgresAppBase):
    __tablename__ = "candidate_snapshots"
    __table_args__ = (
        Index("ix_candidate_snapshots_is_active", "is_active"),
        {"schema": "integration"}
    )

    source_id = Column(String(100), primary_key=True)
    source_hash = Column(String(64), nullable=False)
    source_updated_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    payload = Column(JSONB, nullable=False)

class VacancySnapshot(PostgresAppBase):
    __tablename__ = "vacancy_snapshots"
    __table_args__ = (
        Index("ix_vacancy_snapshots_is_active", "is_active"),
        {"schema": "integration"}
    )

    source_id = Column(String(100), primary_key=True)
    source_hash = Column(String(64), nullable=False)
    source_updated_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    payload = Column(JSONB, nullable=False)
