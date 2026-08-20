import hashlib
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional, cast

from pydantic.json import pydantic_encoder

from app.core.database import MssqlReadSession, PostgresAppSession
from app.models.validation import (
    ShadowValidationRun, ShadowValidationResult, ValidationMetricsSnapshot
)
from app.models.mssql.vacancy import RecruitVacancyCandidateList
from app.schemas.analysis import EnrichedCandidateAnalysis

logger = logging.getLogger("cv_analyzer.shadow")

class DeltaCalculator:
    @staticmethod
    def calculate_score_delta(old_score: Optional[float], new_score: Optional[float]) -> Optional[Decimal]:
        if old_score is None or new_score is None:
            return None
        return Decimal(str(new_score)) - Decimal(str(old_score))

    @staticmethod
    def calculate_classification_delta(old_class: str, new_class: str) -> Optional[str]:
        if old_class == new_class:
            return None
        return f"{old_class} -> {new_class}"

    @staticmethod
    def calculate_dict_diff(old_dict: dict, new_dict: dict) -> dict:
        diff = {}
        all_keys = set(old_dict.keys()).union(new_dict.keys())
        for k in all_keys:
            old_v = old_dict.get(k)
            new_v = new_dict.get(k)
            if old_v != new_v:
                diff[k] = {"old": old_v, "new": new_v}
        return diff


class ShadowEvaluator:
    @classmethod
    def evaluate(
        cls, 
        source_candidate_id: int,
        vacancy_id: Optional[int], 
        old_result: Optional[EnrichedCandidateAnalysis], 
        new_result: EnrichedCandidateAnalysis,
        airis_status_id: Optional[int] = None,
        is_historical: bool = False,
        pg_db = None
    ) -> ShadowValidationResult:
        
        # 1. Compare Scores
        old_score = old_result.best_match.overall_score if old_result and old_result.best_match else None
        new_score = new_result.best_match.overall_score if new_result and new_result.best_match else None
        score_delta = DeltaCalculator.calculate_score_delta(old_score, new_score)

        # 2. Compare Classification
        old_rec = old_result.best_match.recommendation if old_result and old_result.best_match else "NO_MATCH"
        new_rec = new_result.best_match.recommendation if new_result and new_result.best_match else "NO_MATCH"
        
        old_status = str(old_result.match_status.value if hasattr(old_result.match_status, 'value') else old_result.match_status) if old_result else ""
        new_status = str(new_result.match_status.value if hasattr(new_result.match_status, 'value') else new_result.match_status)
        class_delta = DeltaCalculator.calculate_classification_delta(old_status, new_status)

        # 3. Department & Designation Delta
        old_dept = old_result.classification.industry_department if old_result and old_result.classification else None
        new_dept = new_result.classification.industry_department if new_result and new_result.classification else None
        dept_delta = f"{old_dept} -> {new_dept}" if old_dept != new_dept else None

        old_desig = old_result.classification.industry_designation if old_result and old_result.classification else None
        new_desig = new_result.classification.industry_designation if new_result and new_result.classification else None
        desig_delta = f"{old_desig} -> {new_desig}" if old_desig != new_desig else None

        # 4. Reason & Evidence Delta
        old_evidence = [e.dict() for e in old_result.classification.evidence] if old_result and old_result.classification else []
        new_evidence = [e.dict() for e in new_result.classification.evidence] if new_result and new_result.classification else []
        
        reason_delta = {
            "old_evidence": old_evidence,
            "new_evidence": new_evidence
        } if old_evidence != new_evidence else None

        # 5. Calculate Truth Metrics (Against AIRIS)
        airis_is_hired = None
        is_false_positive = None
        is_false_negative = None
        is_agreement = None

        if airis_status_id is not None and pg_db is not None:
            from app.models.validation import AirisHistoricalBenchmark
            benchmark = pg_db.query(AirisHistoricalBenchmark).filter_by(status_id=airis_status_id).first()
            if benchmark:
                airis_is_hired = benchmark.is_hired
                
                cvai_is_positive = (new_rec in ["HIGH", "MEDIUM"])

                if airis_is_hired and not cvai_is_positive:
                    is_false_negative = True
                    is_false_positive = False
                    is_agreement = False
                elif not airis_is_hired and cvai_is_positive:
                    is_false_positive = True
                    is_false_negative = False
                    is_agreement = False
                else:
                    is_false_positive = False
                    is_false_negative = False
                    is_agreement = True

        # Prepare historical mapping details
        historical_airis_result = {
            "status_id": airis_status_id,
            "is_hired": airis_is_hired
        } if airis_status_id is not None else None

        result = ShadowValidationResult(
            airis_status_id=airis_status_id,
            airis_is_hired=airis_is_hired,
            cvai_score=new_score,
            cvai_recommendation=new_rec,
            production_result=json.loads(json.dumps(old_result.dict(), default=pydantic_encoder)) if old_result else None,
            shadow_result=json.loads(json.dumps(new_result.dict(), default=pydantic_encoder)) if new_result else None,
            score_difference=score_delta,
            status_difference=class_delta,
            department_difference=dept_delta,
            designation_difference=desig_delta,
            evidence_difference=reason_delta,
            historical_airis_result=historical_airis_result,
            is_false_positive=is_false_positive,
            is_false_negative=is_false_negative,
            is_agreement=is_agreement
        )

        return result

def execute_shadow_pipeline(source_candidate_id: int, vacancy_id: Optional[int], prod_result_dict: dict, cv_text: str):
    import asyncio
    from rq import get_current_job
    from app.services.match_service import MatchService
    from app.schemas.analysis import EnrichedCandidateAnalysis

    current_job = get_current_job()
    run_id = int(current_job.meta.get("shadow_run_id")) if current_job and current_job.meta.get("shadow_run_id") else None

    try:
        pg_session_factory = cast(Any, PostgresAppSession)
        if pg_session_factory is None:
            raise RuntimeError("PostgreSQL is unavailable for shadow validation persistence.")
        with pg_session_factory() as pg_db:
            run = pg_db.query(ShadowValidationRun).filter(ShadowValidationRun.id == run_id).first() if run_id else None
            if run is not None:
                existing_result = pg_db.query(ShadowValidationResult).filter(ShadowValidationResult.run_id == run.id).first()
                if run.status == "COMPLETED" and existing_result is not None:
                    return {"status": "completed", "run_id": run.id, "reused": True}
                run.status = "RUNNING"
                run.completed_at = None
            else:
                run = ShadowValidationRun(
                    candidate_id=source_candidate_id,
                    vacancy_id=vacancy_id,
                    is_historical=False,
                    status="RUNNING",
                )
                pg_db.add(run)
            pg_db.commit()
            pg_db.refresh(run)
            run_id = run.id

        if current_job is not None:
            current_job.meta["shadow_run_id"] = run_id
            current_job.save_meta()

        prod_result = EnrichedCandidateAnalysis.model_validate(prod_result_dict)
        shadow_result = asyncio.run(MatchService.analyze_single_cv(
            cv_text=cv_text,
            cv_key=f"shadow_source_candidate_{source_candidate_id}",
            source_candidate_id=source_candidate_id,
            _shadow_run=True,
        ))
        airis_status_id = None
        if vacancy_id:
            if MssqlReadSession is None:
                raise RuntimeError("MSSQL is unavailable for shadow AIRIS validation.")
            mssql_session_factory = cast(Any, MssqlReadSession)
            with mssql_session_factory() as mssql_db:
                mapping = mssql_db.query(RecruitVacancyCandidateList).filter(
                    RecruitVacancyCandidateList.CandidateID == source_candidate_id,
                    RecruitVacancyCandidateList.VacancyRequestID == vacancy_id,
                ).first()
                if mapping:
                    airis_status_id = mapping.StatusID

        with pg_session_factory() as pg_db:
            run = pg_db.query(ShadowValidationRun).filter(ShadowValidationRun.id == run_id).one()
            existing_result = pg_db.query(ShadowValidationResult).filter(ShadowValidationResult.run_id == run.id).first()
            if existing_result is None:
                eval_result = ShadowEvaluator.evaluate(
                    source_candidate_id=source_candidate_id,
                    vacancy_id=vacancy_id,
                    old_result=prod_result,
                    new_result=shadow_result,
                    airis_status_id=airis_status_id,
                    pg_db=pg_db,
                )
                eval_result.run_id = run.id
                pg_db.add(eval_result)
            run.status = "COMPLETED"
            run.completed_at = datetime.now(timezone.utc)
            pg_db.commit()
        return {"status": "completed", "run_id": run_id, "reused": existing_result is not None}
    except Exception as e:
        logger.error(f"Shadow validation pipeline failed: {e}", exc_info=True)
        if run_id is not None and PostgresAppSession is not None:
            try:
                with cast(Any, PostgresAppSession)() as pg_db:
                    failed_run = pg_db.query(ShadowValidationRun).filter(ShadowValidationRun.id == run_id).first()
                    if failed_run is not None:
                        failed_run.status = "FAILED"
                        failed_run.completed_at = datetime.now(timezone.utc)
                        pg_db.commit()
            except Exception as status_exc:
                logger.error(f"Could not persist failed shadow run {run_id}: {status_exc}")
        raise

class ShadowValidationService:
    @classmethod
    def enqueue_shadow_validation(
        cls, 
        source_candidate_id: int,
        vacancy_id: Optional[int], 
        prod_result_dict: dict,
        cv_text: str
    ) -> bool:
        """
        Enqueues the shadow validation comparison via RQ to prevent unmanaged threads.
        """
        job_id = None
        connection = None
        try:
            from rq import Queue, Retry
            from redis import Redis
            from app.core.config import settings
            
            if not settings.REDIS_URL:
                logger.warning("REDIS_URL not set. Shadow validation will not be queued.")
                return False

            connection = Redis.from_url(
                settings.REDIS_URL,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
                socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
                health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS,
            )
            queue = Queue(settings.RQ_SHADOW_QUEUE_NAME, connection=connection)
            payload_hash = hashlib.sha256(
                json.dumps(prod_result_dict, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()[:16]
            job_id = f"shadow-{source_candidate_id}-{vacancy_id or 0}-{payload_hash}"
            queue.enqueue(
                execute_shadow_pipeline,
                source_candidate_id=source_candidate_id,
                vacancy_id=vacancy_id,
                prod_result_dict=prod_result_dict,
                cv_text=cv_text,
                retry=Retry(
                    max=settings.SHADOW_VALIDATION_MAX_RETRIES,
                    interval=settings.SHADOW_VALIDATION_RETRY_INTERVAL_SECONDS,
                ),
                job_timeout=settings.SHADOW_VALIDATION_JOB_TIMEOUT_SECONDS,
                result_ttl=settings.RQ_RESULT_TTL_SECONDS,
                job_id=job_id,
                unique=True,
            )
            return True
        except Exception as e:
            try:
                from rq.job import Job

                if not job_id or connection is None:
                    raise LookupError("Shadow job identity was not created.")
                Job.fetch(job_id, connection=connection)
                logger.info(f"Shadow validation job '{job_id}' is already queued or retained.")
                return True
            except Exception:
                logger.error(f"Failed to enqueue shadow validation: {e}")
            return False

class MetricsEngine:
    @classmethod
    def snapshot_metrics(cls):
        """Calculates explicit global TP, TN, FP, FNR and stores a snapshot."""
        pg_session_factory = cast(Any, PostgresAppSession)
        if pg_session_factory is None:
            raise RuntimeError("PostgreSQL is unavailable for validation metrics persistence.")
        with pg_session_factory() as pg_db:
            total = pg_db.query(ShadowValidationResult).filter(ShadowValidationResult.is_agreement.isnot(None)).count()
            if total == 0:
                return
            
            # True Positive (TP): CV-AI predicted match, AIRIS was hired
            tp = pg_db.query(ShadowValidationResult).filter(
                ShadowValidationResult.is_agreement == True,
                ShadowValidationResult.airis_is_hired == True
            ).count()
            
            # True Negative (TN): CV-AI predicted no-match, AIRIS was not hired
            tn = pg_db.query(ShadowValidationResult).filter(
                ShadowValidationResult.is_agreement == True,
                ShadowValidationResult.airis_is_hired == False
            ).count()

            # False Positive (FP): CV-AI predicted match, AIRIS was not hired
            fp = pg_db.query(ShadowValidationResult).filter(ShadowValidationResult.is_false_positive == True).count()
            
            # False Negative (FN): CV-AI predicted no-match, AIRIS was hired
            fn = pg_db.query(ShadowValidationResult).filter(ShadowValidationResult.is_false_negative == True).count()
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
            fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
            
            agreement_rate = (tp + tn) / total if total > 0 else 0
            
            # No-match accuracy: correctly identifying when a candidate is NOT a match
            no_match_accuracy = tn / (tn + fp) if (tn + fp) > 0 else 0

            snap = ValidationMetricsSnapshot(
                total_runs=total,
                false_positive_rate=fpr,
                false_negative_rate=fnr,
                agreement_rate=agreement_rate,
                precision=precision,
                recall=recall,
                no_match_accuracy=no_match_accuracy
            )
            pg_db.add(snap)
            pg_db.commit()
