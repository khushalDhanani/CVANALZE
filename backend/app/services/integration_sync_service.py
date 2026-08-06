import logging
import json
import hashlib
from typing import Type, List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, func, and_
from pydantic import BaseModel
from pydantic.json import pydantic_encoder

from app.core.database import MssqlReadSession, PostgresAppSession
from app.models.integration import (
    SyncRun, SyncWatermark, SyncError,
    DepartmentSnapshot, DesignationSnapshot, JobProfileSnapshot,
    CandidateSnapshot, VacancySnapshot
)
from app.models.mssql.organization import OrgDepartmentMst, OrgDesignationMst, OrgJobProfileMst
from app.models.mssql.candidate import RecruitCandidateMst
from app.models.mssql.vacancy import RecruitVacancyRequest

logger = logging.getLogger("cv_analyzer.integration")

class BaseSyncService:
    ENTITY_TYPE = "base"
    SNAPSHOT_MODEL = None
    MSSQL_MODEL = None
    MSSQL_ID_COL = None
    MSSQL_UPDATED_COL = None
    MSSQL_CREATED_COL = None
    MSSQL_IS_ACTIVE_COL = None

    @classmethod
    def serialize_payload(cls, record) -> dict:
        """Serialize MSSQL SQLAlchemy model to dict."""
        return {c.name: getattr(record, c.name) for c in record.__table__.columns}

    @classmethod
    def _compute_hash(cls, payload: dict) -> str:
        """Compute stable hash for idempotency check."""
        serialized = json.dumps(payload, default=str, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def get_watermark(cls, pg_db) -> Optional[datetime]:
        wm = pg_db.query(SyncWatermark).filter(SyncWatermark.entity_type == cls.ENTITY_TYPE).first()
        return wm.last_source_updated_at if wm else None

    @classmethod
    def set_watermark(cls, pg_db, dt: datetime):
        if not dt:
            return
        wm = pg_db.query(SyncWatermark).filter(SyncWatermark.entity_type == cls.ENTITY_TYPE).first()
        if wm:
            if dt > wm.last_source_updated_at:
                wm.last_source_updated_at = dt
        else:
            wm = SyncWatermark(entity_type=cls.ENTITY_TYPE, last_source_updated_at=dt)
            pg_db.add(wm)
        pg_db.flush()

    @classmethod
    def _get_updated_timestamp(cls, record) -> datetime:
        dt = getattr(record, cls.MSSQL_UPDATED_COL.name) or getattr(record, cls.MSSQL_CREATED_COL.name)
        # Ensure timezone-aware for Postgres
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt or datetime.now(timezone.utc)

    @classmethod
    def run_sync(cls) -> dict:
        """Executes the synchronization process for this entity."""
        if MssqlReadSession is None or PostgresAppSession is None:
            logger.warning("Database sessions not available for sync.")
            return {"status": "skipped", "reason": "No DB connection"}

        metrics = {"records_processed": 0, "errors": 0, "inserted": 0, "updated": 0, "deactivated": 0}

        with PostgresAppSession() as pg_db:
            run = SyncRun(entity_type=cls.ENTITY_TYPE, status="RUNNING")
            pg_db.add(run)
            pg_db.commit()
            pg_db.refresh(run)

            try:
                watermark = cls.get_watermark(pg_db)
                max_updated = watermark

                with MssqlReadSession() as mssql_db:
                    query = mssql_db.query(cls.MSSQL_MODEL)
                    
                    if watermark:
                        # Only records modified after the watermark
                        coalesced_dt = func.coalesce(cls.MSSQL_UPDATED_COL, cls.MSSQL_CREATED_COL)
                        query = query.filter(coalesced_dt > watermark)

                    # Order by timestamp to safely track watermark during partial failures
                    coalesced_dt = func.coalesce(cls.MSSQL_UPDATED_COL, cls.MSSQL_CREATED_COL)
                    query = query.order_by(coalesced_dt.asc())

                    source_records = query.yield_per(1000)
                    lowest_failed_timestamp = None

                    for record in source_records:
                        metrics["records_processed"] += 1
                        try:
                            with pg_db.begin_nested():
                                source_id = str(getattr(record, cls.MSSQL_ID_COL.name))
                                payload = cls.serialize_payload(record)
                                payload_hash = cls._compute_hash(payload)
                                record_updated = cls._get_updated_timestamp(record)

                                is_active = True
                                if cls.MSSQL_IS_ACTIVE_COL:
                                    is_active = getattr(record, cls.MSSQL_IS_ACTIVE_COL.name)

                                # Check if exists in snapshot
                                snapshot = pg_db.query(cls.SNAPSHOT_MODEL).filter(cls.SNAPSHOT_MODEL.source_id == source_id).first()

                                if not snapshot:
                                    new_snap = cls.SNAPSHOT_MODEL(
                                        source_id=source_id,
                                        source_hash=payload_hash,
                                        source_updated_at=record_updated,
                                        is_active=is_active,
                                        payload=payload
                                    )
                                    pg_db.add(new_snap)
                                    metrics["inserted"] += 1
                                else:
                                    if snapshot.source_hash != payload_hash or snapshot.is_active != is_active:
                                        snapshot.source_hash = payload_hash
                                        snapshot.source_updated_at = record_updated
                                        snapshot.is_active = is_active
                                        snapshot.payload = payload
                                        metrics["updated"] += 1

                                pg_db.flush()
                                
                                if max_updated is None or record_updated > max_updated:
                                    max_updated = record_updated

                        except Exception as e:
                            metrics["errors"] += 1
                            record_updated = cls._get_updated_timestamp(record)
                            if lowest_failed_timestamp is None or record_updated < lowest_failed_timestamp:
                                lowest_failed_timestamp = record_updated
                                
                            try:
                                with pg_db.begin_nested():
                                    err = SyncError(
                                        sync_run_id=run.id,
                                        entity_type=cls.ENTITY_TYPE,
                                        source_id=str(getattr(record, cls.MSSQL_ID_COL.name, "unknown")),
                                        error_type=type(e).__name__,
                                        error_message=str(e)[:500]
                                    )
                                    pg_db.add(err)
                                    pg_db.flush()
                            except Exception as inner_e:
                                logger.error(f"Failed to record SyncError for {cls.ENTITY_TYPE}: {inner_e}")

                    # Now handle deactivated records by checking against all MSSQL IDs
                    if watermark:
                        # Find source_ids that are in Postgres but not active in MSSQL
                        all_mssql_ids = set(row[0] for row in mssql_db.query(cls.MSSQL_ID_COL).all())
                        pg_active_ids = pg_db.query(cls.SNAPSHOT_MODEL.source_id).filter(cls.SNAPSHOT_MODEL.is_active == True).all()
                        
                        for (pg_id,) in pg_active_ids:
                            # Parse pg_id back to correct type for comparison, but mssql_ids are fetched natively.
                            # So we stringify MSSQL IDs for the set comparison.
                            if pg_id not in {str(x) for x in all_mssql_ids}:
                                snap = pg_db.query(cls.SNAPSHOT_MODEL).filter(cls.SNAPSHOT_MODEL.source_id == pg_id).first()
                                snap.is_active = False
                                metrics["deactivated"] += 1

                if max_updated:
                    if lowest_failed_timestamp and lowest_failed_timestamp < max_updated:
                        cls.set_watermark(pg_db, lowest_failed_timestamp)
                    else:
                        cls.set_watermark(pg_db, max_updated)

                run.status = "COMPLETED"
                run.completed_at = datetime.now(timezone.utc)
                run.records_processed = metrics["records_processed"]
                run.error_count = metrics["errors"]
                pg_db.commit()

            except Exception as e:
                pg_db.rollback()
                logger.error(f"Sync failed for {cls.ENTITY_TYPE}: {e}", exc_info=True)
                run.status = "FAILED"
                run.completed_at = datetime.now(timezone.utc)
                run.error_count = metrics["errors"]
                
                # We need a new session to save the failed run status if the transaction was rolled back
                with PostgresAppSession() as pg_db_err:
                    err_run = pg_db_err.query(SyncRun).get(run.id)
                    if err_run:
                        err_run.status = "FAILED"
                        err_run.completed_at = run.completed_at
                        err_run.error_count = run.error_count
                        pg_db_err.commit()

        return metrics

class DepartmentSync(BaseSyncService):
    ENTITY_TYPE = "department"
    SNAPSHOT_MODEL = DepartmentSnapshot
    MSSQL_MODEL = OrgDepartmentMst
    MSSQL_ID_COL = OrgDepartmentMst.DeptID
    MSSQL_UPDATED_COL = OrgDepartmentMst.DeptUpdDt
    MSSQL_CREATED_COL = OrgDepartmentMst.DeptEntDt
    MSSQL_IS_ACTIVE_COL = OrgDepartmentMst.DeptIsActive

class DesignationSync(BaseSyncService):
    ENTITY_TYPE = "designation"
    SNAPSHOT_MODEL = DesignationSnapshot
    MSSQL_MODEL = OrgDesignationMst
    MSSQL_ID_COL = OrgDesignationMst.DesigID
    MSSQL_UPDATED_COL = OrgDesignationMst.DesigUpdDt
    MSSQL_CREATED_COL = OrgDesignationMst.DesigEntDt
    MSSQL_IS_ACTIVE_COL = OrgDesignationMst.DesigIsActive

class JobProfileSync(BaseSyncService):
    ENTITY_TYPE = "job_profile"
    SNAPSHOT_MODEL = JobProfileSnapshot
    MSSQL_MODEL = OrgJobProfileMst
    MSSQL_ID_COL = OrgJobProfileMst.JobProfileID
    MSSQL_UPDATED_COL = OrgJobProfileMst.JobProfileUpdDt
    MSSQL_CREATED_COL = OrgJobProfileMst.JobProfileEntDt
    MSSQL_IS_ACTIVE_COL = OrgJobProfileMst.JobProfileIsActive

class ReferenceSyncService:
    @classmethod
    def sync_all(cls) -> dict:
        results = {}
        results["departments"] = DepartmentSync.run_sync()
        results["designations"] = DesignationSync.run_sync()
        results["job_profiles"] = JobProfileSync.run_sync()
        return results

class CandidateSyncService(BaseSyncService):
    ENTITY_TYPE = "candidate"
    SNAPSHOT_MODEL = CandidateSnapshot
    MSSQL_MODEL = RecruitCandidateMst
    MSSQL_ID_COL = RecruitCandidateMst.CandidateID
    MSSQL_UPDATED_COL = RecruitCandidateMst.CandidateUpdDt
    MSSQL_CREATED_COL = RecruitCandidateMst.CandidateEntDt
    MSSQL_IS_ACTIVE_COL = RecruitCandidateMst.CandidateIsActive

    @classmethod
    def serialize_payload(cls, record) -> dict:
        """Allowlist explicit fields to prevent PII duplication in JSON snapshot."""
        allowlist = {
            "CandidateID", "NoticePeriodID", "MainDeptID", "DeptID", "DesigID",
            "CandidateDomainKnowlgID", "CandidateJobProfileID", "CandidateTotExperience",
            "CandidateExpectedCtc", "CandidateLanguageKnown", "CandidateHighestQualificationID",
            "CandidateStatusID", "CandidateIsActive"
        }
        return {c.name: getattr(record, c.name) for c in record.__table__.columns if c.name in allowlist}

class VacancySyncService(BaseSyncService):
    ENTITY_TYPE = "vacancy"
    SNAPSHOT_MODEL = VacancySnapshot
    MSSQL_MODEL = RecruitVacancyRequest
    MSSQL_ID_COL = RecruitVacancyRequest.VacancyRequestID
    MSSQL_UPDATED_COL = RecruitVacancyRequest.VacencyRequestUpdDt
    MSSQL_CREATED_COL = RecruitVacancyRequest.VacencyRequestEntDt
    MSSQL_IS_ACTIVE_COL = RecruitVacancyRequest.VacancyRequestIsActive

class SourceFreshnessService:
    @classmethod
    def check_freshness(cls, entity_type: str, max_age_seconds: int = 3600) -> dict:
        """Returns warnings or SOURCE_DATA_UNAVAILABLE if the data is stale."""
        with PostgresAppSession() as pg_db:
            wm = pg_db.query(SyncWatermark).filter(SyncWatermark.entity_type == entity_type).first()
            if not wm:
                return {"status": "SOURCE_DATA_UNAVAILABLE", "message": f"No sync data available for {entity_type}."}
            
            age = (datetime.now(timezone.utc) - wm.synced_at).total_seconds()
            if age > max_age_seconds:
                return {"status": "STALE_SOURCE", "message": f"Data for {entity_type} is stale. Last synced {age} seconds ago."}
            
            return {"status": "FRESH", "message": "Data is fresh."}
