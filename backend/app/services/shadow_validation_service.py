import logging
import json
from decimal import Decimal
from datetime import datetime, timezone
from pydantic.json import pydantic_encoder
from typing import Optional

from app.core.database import PostgresAppSession, MssqlReadSession
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
        candidate_id: int, 
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
        
        old_status = (old_result.match_status.value if hasattr(old_result.match_status, 'value') else old_result.match_status) if old_result else None
        new_status = (new_result.match_status.value if hasattr(new_result.match_status, 'value') else new_result.match_status) if new_result else None
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

def execute_shadow_pipeline(candidate_id: int, vacancy_id: Optional[int], prod_result_dict: dict, cv_text: str):
    import asyncio
    from app.services.match_service import MatchService
    from app.schemas.analysis import EnrichedCandidateAnalysis
    
    # 1. Parse prod_result
    prod_result = EnrichedCandidateAnalysis.model_validate(prod_result_dict)
    
    # 2. Run shadow pipeline independently
    try:
        shadow_result = asyncio.run(MatchService.analyze_single_cv(
            cv_text=cv_text,
            candidate_id=str(candidate_id)
        ))
    except Exception as e:
        logger.error(f"Shadow pipeline execution failed: {e}")
        raise
        
    # 3. Evaluate and persist
    try:
        with PostgresAppSession() as pg_db:
            airis_status_id = None
            if vacancy_id:
                with MssqlReadSession() as mssql_db:
                    mapping = mssql_db.query(RecruitVacancyCandidateList).filter(
                        RecruitVacancyCandidateList.CandidateID == candidate_id,
                        RecruitVacancyCandidateList.VacancyRequestID == vacancy_id
                    ).first()
                    if mapping:
                        airis_status_id = mapping.StatusID

            run = ShadowValidationRun(
                candidate_id=candidate_id,
                vacancy_id=vacancy_id,
                is_historical=False,
                status="RUNNING"
            )
            pg_db.add(run)
            pg_db.flush()

            eval_result = ShadowEvaluator.evaluate(
                candidate_id=candidate_id,
                vacancy_id=vacancy_id,
                old_result=prod_result,
                new_result=shadow_result,
                airis_status_id=airis_status_id,
                pg_db=pg_db
            )
            
            eval_result.run_id = run.id
            pg_db.add(eval_result)
            
            run.status = "COMPLETED"
            run.completed_at = datetime.now(timezone.utc)
            pg_db.commit()
    except Exception as e:
        logger.error(f"Shadow validation persistence failed: {e}", exc_info=True)
        raise

class ShadowValidationService:
    @classmethod
    def enqueue_shadow_validation(
        cls, 
        candidate_id: int, 
        vacancy_id: Optional[int], 
        prod_result_dict: dict,
        cv_text: str
    ):
        """
        Enqueues the shadow validation comparison via RQ to prevent unmanaged threads.
        """
        try:
            from rq import Queue, Retry
            from redis import Redis
            from app.core.config import settings
            
            if not settings.REDIS_URL:
                logger.warning("REDIS_URL not set. Shadow validation will not be queued.")
                return

            connection = Redis.from_url(settings.REDIS_URL)
            queue = Queue("shadow_validation", connection=connection)
            queue.enqueue(
                execute_shadow_pipeline,
                candidate_id=candidate_id,
                vacancy_id=vacancy_id,
                prod_result_dict=prod_result_dict,
                cv_text=cv_text,
                retry=Retry(max=3, interval=60),
                job_timeout=600
            )
        except Exception as e:
            logger.error(f"Failed to enqueue shadow validation: {e}")

class MetricsEngine:
    @classmethod
    def snapshot_metrics(cls):
        """Calculates explicit global TP, TN, FP, FNR and stores a snapshot."""
        with PostgresAppSession() as pg_db:
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
