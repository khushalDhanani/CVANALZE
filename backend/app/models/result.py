from __future__ import annotations
from sqlalchemy import Column, DateTime, String, JSON, BigInteger, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.core.database import PostgresAppBase

class CVResult(PostgresAppBase):
    __tablename__ = "cv_results"

    cv_key = Column(String, primary_key=True)
    status = Column(String, nullable=True)
    parsed_at = Column(DateTime(timezone=True), server_default=func.now())
    generation_sequence = Column(
        BigInteger,
        nullable=False,
        server_default=text("nextval('cv_results_generation_seq')"),
        index=True,
    )

    full_name = Column(String, nullable=True)
    candidate_id = Column(String, nullable=True)
    cv_id = Column(String, nullable=True)
    cv_hash = Column(String, nullable=True, index=True)

    
    resume_json = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    match_analysis = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    
    text_content = Column(String, nullable=True)
    markdown_content = Column(String, nullable=True)
    raw_data = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
