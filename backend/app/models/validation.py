from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.core.database import PostgresAppBase

class ShadowValidationRun(PostgresAppBase):
    __tablename__ = "shadow_validation_runs"
    __table_args__ = {"schema": "validation"}

    id = Column(BigInteger, primary_key=True, index=True)
    candidate_id = Column(BigInteger, nullable=False)
    vacancy_id = Column(BigInteger, nullable=True) # Optional if it's a general pool evaluation
    is_historical = Column(Boolean, default=False, nullable=False)
    run_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False) # e.g. RUNNING, COMPLETED, FAILED

class ShadowValidationResult(PostgresAppBase):
    __tablename__ = "shadow_validation_results"
    __table_args__ = {"schema": "validation"}

    id = Column(BigInteger, primary_key=True, index=True)
    run_id = Column(BigInteger, ForeignKey("validation.shadow_validation_runs.id"), nullable=False)
    
    # AIRIS Historical Baseline
    airis_status_id = Column(BigInteger, nullable=True)
    airis_is_hired = Column(Boolean, nullable=True)
    
    # CV-Analyzer Results
    cvai_score = Column(Numeric, nullable=True)
    cvai_recommendation = Column(String(50), nullable=True)
    
    # Raw Payloads
    production_result = Column(JSONB, nullable=True)
    shadow_result = Column(JSONB, nullable=True)
    
    # Deltas
    score_difference = Column(Numeric, nullable=True)
    department_difference = Column(String, nullable=True)
    designation_difference = Column(String, nullable=True)
    status_difference = Column(String, nullable=True)
    evidence_difference = Column(JSONB, nullable=True)
    
    # Historical AIRIS mapping
    historical_airis_result = Column(JSONB, nullable=True)
    
    # Calculated Metrics
    is_false_positive = Column(Boolean, nullable=True)
    is_false_negative = Column(Boolean, nullable=True)
    is_agreement = Column(Boolean, nullable=True)

class AirisHistoricalBenchmark(PostgresAppBase):
    __tablename__ = "airis_historical_benchmarks"
    __table_args__ = {"schema": "validation"}

    id = Column(BigInteger, primary_key=True, index=True)
    status_id = Column(BigInteger, nullable=False, unique=True)
    status_name = Column(String(100), nullable=False)
    is_hired = Column(Boolean, nullable=False)
    description = Column(String, nullable=True)

class ValidationMetricsSnapshot(PostgresAppBase):
    __tablename__ = "validation_metrics_snapshots"
    __table_args__ = {"schema": "validation"}

    id = Column(BigInteger, primary_key=True, index=True)
    snapshot_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    total_runs = Column(Integer, nullable=False)
    false_positive_rate = Column(Numeric, nullable=False)
    false_negative_rate = Column(Numeric, nullable=False)
    agreement_rate = Column(Numeric, nullable=False)
    precision = Column(Numeric, nullable=False)
    recall = Column(Numeric, nullable=False)
    no_match_accuracy = Column(Numeric, nullable=False)

class HRDisagreementReview(PostgresAppBase):
    __tablename__ = "hr_disagreement_reviews"
    __table_args__ = {"schema": "validation"}

    id = Column(BigInteger, primary_key=True, index=True)
    result_id = Column(BigInteger, ForeignKey("validation.shadow_validation_results.id"), nullable=False)
    hr_user_id = Column(BigInteger, nullable=False)
    agrees_with_cvai = Column(Boolean, nullable=False)
    review_notes = Column(String, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
