from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String

from app.core.database import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    setting_key = Column(String(100), primary_key=True, index=True)
    setting_value = Column(String(500), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
