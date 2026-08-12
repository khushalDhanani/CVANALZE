from __future__ import annotations
from datetime import timezone, datetime

from sqlalchemy import Column, DateTime, String

from app.core.database import PostgresAppBase


class SystemConfig(PostgresAppBase):
    """
    DEPRECATED: Use RuleConfigProfile (in app.models.rules) for all business rules, thresholds, and weights.
    This legacy key-value table will be removed in Phase 3.
    """
    __tablename__ = "system_config"

    setting_key = Column(String(100), primary_key=True, index=True)
    setting_value = Column(String(500), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
