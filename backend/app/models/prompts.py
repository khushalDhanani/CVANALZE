from datetime import UTC, datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint
from app.core.database import PostgresAppBase


class PromptTemplateMaster(PostgresAppBase):
    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint(
            "prompt_name", "version_tag", "tenant_id", "model", "language", "environment",
            name="uq_prompt_multi_dim"
        ),
        {"schema": "cvai"}
    )

    prompt_id = Column(Integer, primary_key=True, autoincrement=True)
    prompt_name = Column(String(100), nullable=False, index=True)
    version_tag = Column(String(50), nullable=False)
    description = Column(String(500), nullable=True)
    system_instruction = Column(Text, nullable=False)
    expected_schema_json = Column(Text, nullable=True)
    
    # New multi-dimensional compatibility columns
    tenant_id = Column(String(50), nullable=True, index=True)
    model = Column(String(50), nullable=True)
    target_schema = Column(String(100), nullable=True)
    language = Column(String(10), default="en", nullable=False)
    environment = Column(String(50), default="production", nullable=False)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
