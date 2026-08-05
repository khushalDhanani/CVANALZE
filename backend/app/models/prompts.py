from datetime import UTC, datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from app.core.database import Base


class PromptTemplateMaster(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = {"schema": "cvai"}

    prompt_id = Column(Integer, primary_key=True, autoincrement=True)
    prompt_name = Column(String(100), nullable=False, unique=True, index=True)
    version_tag = Column(String(50), nullable=False)
    description = Column(String(500), nullable=True)
    system_instruction = Column(Text, nullable=False)
    expected_schema_json = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
