from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.mssql.organization import (
    OrgCompanyMst,
    OrgLocationMst,
    OrgMainDepartmentMst,
    OrgDepartmentMst,
    OrgDesignationMst,
    OrgJobProfileMst,
    JobProfileDomainKnowledgeDet,
    OrgJobProfileQualificationDet
)

class OrganizationSourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_active_departments(self) -> list[OrgDepartmentMst]:
        return self.db.scalars(
            select(OrgDepartmentMst).where(OrgDepartmentMst.DeptIsActive == True)
        ).all()

    def get_all_designations(self) -> list[OrgDesignationMst]:
        return self.db.scalars(select(OrgDesignationMst)).all()
