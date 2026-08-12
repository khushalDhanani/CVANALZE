from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.mssql.organization import (
    OrgJobProfileMst,
    OrgJobProfileQualificationDet,
    JobProfileDomainKnowledgeDet,
    OrgCompanyMst,
    OrgDepartmentMst,
    OrgDesignationMst
)
from app.models.mssql.taxonomy import QualificationMst, RecruitDomainKnowledgeMst


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
                OrgCompanyMst.CompName,
                OrgJobProfileMst.DeptID,
                OrgDepartmentMst.DeptName,
                OrgJobProfileMst.DesigID,
                OrgDesignationMst.DesigName,
                OrgJobProfileMst.JobProfileIsActive
            )
            .outerjoin(OrgCompanyMst, OrgJobProfileMst.CompID == OrgCompanyMst.CompID)
            .outerjoin(OrgDepartmentMst, OrgJobProfileMst.DeptID == OrgDepartmentMst.DeptID)
            .outerjoin(OrgDesignationMst, OrgJobProfileMst.DesigID == OrgDesignationMst.DesigID)
            .where(OrgJobProfileMst.JobProfileID == job_profile_id)
        )
        row = self.db.execute(stmt).first()
        if not row:
            return None
            
        (
            jp_id, name, desc, comp_id, comp_name, dept_id, dept_name,
            desig_id, desig_name, is_active
        ) = row

        # Required Qualifications
        q_stmt = select(
            OrgJobProfileQualificationDet.QualificationID,
            QualificationMst.QualificationName
        ).outerjoin(
            QualificationMst, OrgJobProfileQualificationDet.QualificationID == QualificationMst.QualificationID
        ).where(
            OrgJobProfileQualificationDet.JobProfileID == job_profile_id,
            OrgJobProfileQualificationDet.QualificationIsDeleted == False
        )
        qualifications = [
            {"qualification_id": r.QualificationID, "name": r.QualificationName}
            for r in self.db.execute(q_stmt).all() if r.QualificationID is not None
        ]

        # Domains
        d_stmt = select(
            JobProfileDomainKnowledgeDet.DomainKnowlgID,
            RecruitDomainKnowledgeMst.DomainKnowlgName
        ).outerjoin(
            RecruitDomainKnowledgeMst, JobProfileDomainKnowledgeDet.DomainKnowlgID == RecruitDomainKnowledgeMst.DomainKnowlgID
        ).where(
            JobProfileDomainKnowledgeDet.JobProfileID == job_profile_id,
            JobProfileDomainKnowledgeDet.JobProfileDomainKnowledgeDetIsActive == True
        )
        domains = [
            {"domain_id": r.DomainKnowlgID, "name": r.DomainKnowlgName}
            for r in self.db.execute(d_stmt).all() if r.DomainKnowlgID is not None
        ]

        return {
            "job_profile_id": jp_id,
            "name": name,
            "description": desc,
            "is_active": is_active,
            "company": {
                "id": comp_id,
                "name": comp_name
            } if comp_id else None,
            "department": {
                "id": dept_id,
                "name": dept_name
            } if dept_id else None,
            "designation": {
                "id": desig_id,
                "name": desig_name
            } if desig_id else None,
            "qualifications": qualifications,
            "domains": domains
        }
