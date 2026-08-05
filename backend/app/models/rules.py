from datetime import UTC, datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint
from app.core.database import Base


class RuleValidationTestCase(Base):
    """
    Stores synthetic smoke test payloads for rule configuration validations.
    """
    __tablename__ = "rule_validation_tests"
    __table_args__ = {"schema": "cvai"}

    test_id = Column(Integer, primary_key=True, autoincrement=True)
    test_name = Column(String(255), nullable=False, unique=True)
    target_component = Column(String(100), nullable=False)  # e.g., "location_field", "job_title", "cross_domain"
    payload_json = Column(Text, nullable=False)
    expected_result_json = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class RuleConfigProfile(Base):
    """
    Stores the unified rule configuration JSON in the database, allowing admins to edit
    rules dynamically without modifying the codebase.
    """
    __tablename__ = "rule_config_profiles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "version_tag", name="uq_rule_config_tenant_version"),
        {"schema": "cvai"}
    )

    profile_id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(50), nullable=True, index=True)
    version_tag = Column(String(50), nullable=False)
    description = Column(String(500), nullable=True)
    
    # Store the sections of UnifiedRuleConfig
    global_confidence_tiers_json = Column(Text, nullable=False)
    fields_config_json = Column(Text, nullable=False)
    scoring_rules_json = Column(Text, nullable=False)
    
    is_active = Column(Boolean, default=False)
    
    # Audit fields
    created_by = Column(String(100), nullable=True)
    audit_reason = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
