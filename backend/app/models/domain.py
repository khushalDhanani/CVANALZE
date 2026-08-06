from __future__ import annotations
from datetime import timezone, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)

from app.core.database import PostgresAppBase


from sqlalchemy.dialects.postgresql import JSONB

class DepartmentDomainMaster(PostgresAppBase):
    """
    DB-driven configuration mapping departments to professional domains.

    Replaces the legacy hardcoded DEPARTMENT_DOMAIN_MAP in ScoringEngine so that
    new departments/domains can be added purely via database rows (no code/deploy).
    Keywords and DefaultRoles are stored as JSONB.
    """

    __tablename__ = "DepartmentDomainMaster"

    Id = Column(BigInteger, primary_key=True, autoincrement=True)
    DepartmentId = Column(BigInteger, index=True, nullable=True) # Maps to MSSQL OrgDepartmentMst.DeptID without ForeignKey
    DepartmentNameSnapshot = Column(String(200), nullable=True)
    DomainName = Column(String(200), nullable=False)
    Keywords = Column(JSONB, nullable=False)
    DefaultRoles = Column(JSONB, nullable=False)
    Priority = Column(Integer, nullable=False, default=0)
    IsActive = Column(Boolean, nullable=False, default=True)
    CreatedOn = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    ModifiedOn = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
