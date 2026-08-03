from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class DomainMaster(Base):
    __tablename__ = "domains"
    __table_args__ = {"schema": "cvai"}

    domain_id = Column(Integer, primary_key=True, autoincrement=True)
    domain_code = Column(String(50), nullable=False, unique=True)
    domain_name = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    families = relationship("JobFamilyMaster", back_populates="domain", cascade="all, delete-orphan")


class JobFamilyMaster(Base):
    __tablename__ = "job_families"
    __table_args__ = {"schema": "cvai"}

    family_id = Column(Integer, primary_key=True, autoincrement=True)
    domain_id = Column(
        Integer,
        ForeignKey("cvai.domains.domain_id", ondelete="CASCADE"),
        nullable=False,
    )
    family_code = Column(String(50), nullable=False, unique=True)
    family_name = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    domain = relationship("DomainMaster", back_populates="families")
    designations = relationship("DesignationMaster", back_populates="family", cascade="all, delete-orphan")


class DesignationMaster(Base):
    __tablename__ = "designations"
    __table_args__ = {"schema": "cvai"}

    designation_id = Column(Integer, primary_key=True, autoincrement=True)
    family_id = Column(
        Integer,
        ForeignKey("cvai.job_families.family_id", ondelete="CASCADE"),
        nullable=False,
    )
    designation_code = Column(String(100), nullable=False, unique=True)
    designation_name = Column(String(255), nullable=False)
    seniority_level = Column(String(50), nullable=True)
    content_hash = Column(String(64), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    family = relationship("JobFamilyMaster", back_populates="designations")
    synonyms = relationship("DesignationSynonym", back_populates="designation", cascade="all, delete-orphan")
    skills = relationship("DesignationSkill", back_populates="designation", cascade="all, delete-orphan")


class DesignationSynonym(Base):
    __tablename__ = "designation_synonyms"
    __table_args__ = {"schema": "cvai"}

    synonym_id = Column(Integer, primary_key=True, autoincrement=True)
    designation_id = Column(
        Integer,
        ForeignKey("cvai.designations.designation_id", ondelete="CASCADE"),
        nullable=False,
    )
    synonym_text = Column(String(255), nullable=False, index=True)
    is_canonical = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    designation = relationship("DesignationMaster", back_populates="synonyms")


class SkillMaster(Base):
    __tablename__ = "skills"
    __table_args__ = {"schema": "cvai"}

    skill_id = Column(Integer, primary_key=True, autoincrement=True)
    domain_id = Column(Integer, ForeignKey("cvai.domains.domain_id"), nullable=True)
    skill_name = Column(String(255), nullable=False, unique=True)
    category = Column(String(100), default="general")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class DesignationSkill(Base):
    __tablename__ = "designation_skills"
    __table_args__ = {"schema": "cvai"}

    designation_id = Column(
        Integer,
        ForeignKey("cvai.designations.designation_id", ondelete="CASCADE"),
        primary_key=True,
    )
    skill_id = Column(
        Integer,
        ForeignKey("cvai.skills.skill_id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_mandatory = Column(Boolean, default=False)
    importance_weight = Column(Float, default=1.0)

    designation = relationship("DesignationMaster", back_populates="skills")
    skill = relationship("SkillMaster")


class FamilyCompatibility(Base):
    __tablename__ = "family_compatibilities"
    __table_args__ = {"schema": "cvai"}

    source_family_id = Column(Integer, ForeignKey("cvai.job_families.family_id"), primary_key=True)
    target_family_id = Column(Integer, ForeignKey("cvai.job_families.family_id"), primary_key=True)
    compatibility_score = Column(Float, nullable=False, default=1.0)
    is_allowed = Column(Boolean, default=True)
