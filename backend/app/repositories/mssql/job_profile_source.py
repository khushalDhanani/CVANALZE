from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.mssql.organization import (
    OrgJobProfileMst,
    OrgJobProfileQualificationDet,
    JobProfileDomainKnowledgeDet
)

class JobProfileSourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_job_profile_aggregate(self, job_profile_id: int) -> dict | None:
        stmt = (
            select(
                OrgJobProfileMst.JobProfileID,
                OrgJobProfileMst.JobProfileName,
                OrgJobProfileMst.JobProfileDesc,
                OrgJobProfileMst.CompID,
                OrgJobProfileMst.DeptID,
                OrgJobProfileMst.DesigID,
                OrgJobProfileMst.JobProfileIsActive
            )
            .where(OrgJobProfileMst.JobProfileID == job_profile_id)
        )
        row = self.db.execute(stmt).first()
        if not row:
            return None
            
        (
            jp_id, name, desc, comp_id, dept_id, desig_id, is_active
        ) = row

        q_stmt = select(OrgJobProfileQualificationDet.QualificationID).where(
            OrgJobProfileQualificationDet.JobProfileID == job_profile_id,
            OrgJobProfileQualificationDet.QualificationIsDeleted == False
        )
        qualifications = [q for q, in self.db.execute(q_stmt).all() if q is not None]

        d_stmt = select(JobProfileDomainKnowledgeDet.DomainKnowlgID).where(
            JobProfileDomainKnowledgeDet.JobProfileID == job_profile_id,
            JobProfileDomainKnowledgeDet.JobProfileDomainKnowledgeDetIsActive == True
        )
        domains = [d for d, in self.db.execute(d_stmt).all() if d is not None]

        return {
            "job_profile_id": jp_id,
            "name": name,
            "description": desc,
            "company_id": comp_id,
            "department_id": dept_id,
            "designation_id": desig_id,
            "is_active": is_active,
            "qualifications": qualifications,
            "domains": domains
        }
