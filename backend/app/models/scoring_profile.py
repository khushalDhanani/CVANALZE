from __future__ import annotations
from datetime import timezone, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.core.database import PostgresAppBase


class StopWord(PostgresAppBase):
    __tablename__ = "stop_words"
    __table_args__ = {"schema": "cvai"}

    stopword_id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String(100), nullable=False, unique=True, index=True)
    category = Column(String(100), default="prefilter")
    language = Column(String(10), default="en")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ScoringProfileMaster(PostgresAppBase):
    __tablename__ = "scoring_profiles"
    __table_args__ = {"schema": "cvai"}

    profile_id = Column(Integer, primary_key=True, autoincrement=True)
    profile_code = Column(String(50), nullable=False, unique=True)
    profile_name = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    lexical_weights_json = Column(String, nullable=True)
    component_weights_json = Column(String, nullable=True)
    penalties_json = Column(String, nullable=True)
    thresholds_json = Column(String, nullable=True)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
