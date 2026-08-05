from datetime import UTC, datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import PostgresAppBase


class RuleValidationTestCase(PostgresAppBase):
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


class RuleConfigProfile(PostgresAppBase):
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
    
    components = relationship("RuleComponent", back_populates="profile", cascade="all, delete-orphan")
    
    is_active = Column(Boolean, default=False)
    status = Column(String(50), default="DRAFT")
    
    # Audit fields
    created_by = Column(String(100), nullable=True)
    activated_by = Column(String(100), nullable=True)
    activated_at = Column(DateTime, nullable=True)
    activation_reason = Column(String(500), nullable=True)
    previous_version_tag = Column(String(50), nullable=True)
    audit_reason = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class RuleComponent(PostgresAppBase):
    """Normalized table replacing top-level sections (e.g., 'role', 'job_title', 'skills')."""
    __tablename__ = "rule_components"
    __table_args__ = {"schema": "cvai"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("cvai.rule_config_profiles.profile_id", ondelete="CASCADE"), nullable=False)
    component_type = Column(String(50), nullable=False)
    component_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)

    profile = relationship("RuleConfigProfile", back_populates="components")
    system_rules = relationship("SystemRule", back_populates="component", cascade="all, delete-orphan")
    thresholds = relationship("RuleThreshold", back_populates="component", cascade="all, delete-orphan")
    penalties = relationship("RulePenalty", back_populates="component", cascade="all, delete-orphan")
    weights = relationship("RuleWeight", back_populates="component", cascade="all, delete-orphan")


class SystemRule(PostgresAppBase):
    """Normalized table for specific business rules (e.g., 'cross_domain_guard', 'vacancy_taxonomy')."""
    __tablename__ = "system_rules"
    __table_args__ = {"schema": "cvai"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    component_id = Column(Integer, ForeignKey("cvai.rule_components.id", ondelete="CASCADE"), nullable=False)
    rule_type = Column(String(50), nullable=False)
    rule_name = Column(String(100), nullable=False)
    target_value = Column(String(255), nullable=True)

    component = relationship("RuleComponent", back_populates="system_rules")
    conditions = relationship("RuleCondition", back_populates="rule", cascade="all, delete-orphan")


class RuleCondition(PostgresAppBase):
    """Normalized table for rule conditions (e.g., taxonomy rule branches)."""
    __tablename__ = "rule_conditions"
    __table_args__ = {"schema": "cvai"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey("cvai.system_rules.id", ondelete="CASCADE"), nullable=False)
    condition_scope = Column(String(100), nullable=False)
    condition_mode = Column(String(50), nullable=False, default="any")
    keywords_json = Column(Text, nullable=True)
    is_negated = Column(Boolean, default=False)

    rule = relationship("SystemRule", back_populates="conditions")


class RuleThreshold(PostgresAppBase):
    """Normalized table for thresholds (e.g., high_min, low_coverage_threshold)."""
    __tablename__ = "rule_thresholds"
    __table_args__ = {"schema": "cvai"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    component_id = Column(Integer, ForeignKey("cvai.rule_components.id", ondelete="CASCADE"), nullable=False)
    threshold_key = Column(String(100), nullable=False)
    threshold_value = Column(Float, nullable=False)

    component = relationship("RuleComponent", back_populates="thresholds")


class RulePenalty(PostgresAppBase):
    """Normalized table for penalties (e.g., domain_mismatch_multiplier)."""
    __tablename__ = "rule_penalties"
    __table_args__ = {"schema": "cvai"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    component_id = Column(Integer, ForeignKey("cvai.rule_components.id", ondelete="CASCADE"), nullable=False)
    penalty_key = Column(String(100), nullable=False)
    penalty_value = Column(Float, nullable=False)

    component = relationship("RuleComponent", back_populates="penalties")


class RuleWeight(PostgresAppBase):
    """Normalized table for weights (e.g., semantic weights, contact weights)."""
    __tablename__ = "rule_weights"
    __table_args__ = {"schema": "cvai"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    component_id = Column(Integer, ForeignKey("cvai.rule_components.id", ondelete="CASCADE"), nullable=False)
    weight_key = Column(String(100), nullable=False)
    weight_value = Column(Float, nullable=False)

    component = relationship("RuleComponent", back_populates="weights")
