import logging
import json
from decimal import Decimal
from datetime import datetime, timezone
from pydantic.json import pydantic_encoder
from typing import Optional, Dict, Any, Tuple

from app.core.database import PostgresAppBase, PostgresAppSession, MssqlReadSession
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
        is_historical: bool = False
    ) -> ShadowValidationResult:
        
        # 1. Compare Scores (Assuming best_match contains the score)
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
        # Assuming AIRIS status: e.g. 1=Hired, 2=Rejected (Mock logic, depends on AirisHistoricalBenchmark mapping)
        # If airis_status_id is provided, we can map it.
        # Let's say status_id == 5 is 'Hired/Selected' for the sake of metric calculation
        airis_is_hired = None
        is_false_positive = None
        is_false_negative = None
        is_agreement = None

        if airis_status_id is not None:
            # Simple heuristic for demonstration: Assume any status indicating moving forward is a positive
            airis_is_hired = (airis_status_id in [4, 5, 6, 7]) # Placeholder standard IDs
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

        result = ShadowValidationResult(
            airis_status_id=airis_status_id,
            airis_is_hired=airis_is_hired,
            cvai_score=new_score,
            cvai_recommendation=new_rec,
            old_result_payload=json.loads(json.dumps(old_result.dict(), default=pydantic_encoder)) if old_result else None,
            new_result_payload=json.loads(json.dumps(new_result.dict(), default=pydantic_encoder)) if new_result else None,
            score_delta=score_delta,
            classification_delta=class_delta,
            department_delta=dept_delta,
            designation_delta=desig_delta,
            reason_and_evidence_delta=reason_delta,
            is_false_positive=is_false_positive,
            is_false_negative=is_false_negative,
            is_agreement=is_agreement
        )

        return result


class ShadowValidationService:
    @classmethod
    def run_shadow_validation(
        cls, 
        candidate_id: int, 
        vacancy_id: Optional[int], 
        prod_result: EnrichedCandidateAnalysis,
        shadow_result: EnrichedCandidateAnalysis
    ):
        """
        Runs the shadow validation comparison and persists it asynchronously.
        Does not block production execution.
        """
        try:
            with PostgresAppSession() as pg_db:
                # Get historical AIRIS status if available
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
                    airis_status_id=airis_status_id
                )
                
                eval_result.run_id = run.id
                pg_db.add(eval_result)
                
                run.status = "COMPLETED"
                run.completed_at = datetime.now(timezone.utc)
                pg_db.commit()

        except Exception as e:
            logger.error(f"Shadow validation failed: {e}", exc_info=True)


class MetricsEngine:
    @classmethod
    def snapshot_metrics(cls):
        """Calculates global FPR, FNR, etc and stores a snapshot."""
        with PostgresAppSession() as pg_db:
            total = pg_db.query(ShadowValidationResult).filter(ShadowValidationResult.is_agreement.isnot(None)).count()
            if total == 0:
                return
            
            agreements = pg_db.query(ShadowValidationResult).filter(ShadowValidationResult.is_agreement == True).count()
            fps = pg_db.query(ShadowValidationResult).filter(ShadowValidationResult.is_false_positive == True).count()
            fns = pg_db.query(ShadowValidationResult).filter(ShadowValidationResult.is_false_negative == True).count()
            
            # Simple standard metrics
            precision = (agreements) / (agreements + fps) if (agreements + fps) > 0 else 0
            recall = (agreements) / (agreements + fns) if (agreements + fns) > 0 else 0
            fpr = fps / total
            fnr = fns / total
            agreement_rate = agreements / total
            
            # No-match accuracy: correctly identifying when a candidate is NOT a match
            # True Negatives / (True Negatives + False Positives)
            tns = pg_db.query(ShadowValidationResult).filter(
                ShadowValidationResult.is_agreement == True,
                ShadowValidationResult.airis_is_hired == False
            ).count()
            
            no_match_accuracy = tns / (tns + fps) if (tns + fps) > 0 else 0

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
