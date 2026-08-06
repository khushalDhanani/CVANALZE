from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.mssql.candidate import (
    RecruitCandidateMst,
    RecruitCandidateExperienceDet,
    RecruitCandidateQualificationDet,
    RecruitCandidateSkillDet,
    RecruitCandidateLanguageDet,
    RecruitCandidateLocationMst,
    RecruitCandidateNoticePeriodMst
)
from app.models.mssql.organization import OrgJobProfileMst

class CandidateSourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_candidate_aggregate(self, candidate_id: int) -> dict | None:
        stmt = (
            select(
                RecruitCandidateMst.CandidateID,
                RecruitCandidateMst.CandidateFirstName,
                RecruitCandidateMst.CandidateLastName,
                RecruitCandidateMst.CandidateJobProfileID,
                RecruitCandidateMst.CandidateTotExperience,
                RecruitCandidateMst.CandidateExpectedCtc,
                RecruitCandidateMst.CandidateIsActive,
                RecruitCandidateMst.CandidateStatusID,
                OrgJobProfileMst.JobProfileName,
                RecruitCandidateMst.CandidateDomainKnowlgID
            )
            .outerjoin(
                OrgJobProfileMst,
                RecruitCandidateMst.CandidateJobProfileID == OrgJobProfileMst.JobProfileID
            )
            .where(RecruitCandidateMst.CandidateID == candidate_id)
        )
        row = self.db.execute(stmt).first()
        if not row:
            return None
            
        candidate_id, first_name, last_name, job_profile_id, total_exp, expected_ctc, is_active, status_id, jp_name, domain_id = row

        q_stmt = select(RecruitCandidateQualificationDet.QualificationID).where(
            RecruitCandidateQualificationDet.CandidateID == candidate_id,
            RecruitCandidateQualificationDet.CandidQualiIsActive == True,
            RecruitCandidateQualificationDet.CandidQualiIsDeleted == False
        )
        qualifications = [q for q, in self.db.execute(q_stmt).all() if q is not None]

        s_stmt = select(RecruitCandidateSkillDet.SkillID).where(
            RecruitCandidateSkillDet.CandidateID == candidate_id,
            RecruitCandidateSkillDet.CandidateSkillIsActive == True,
            RecruitCandidateSkillDet.CandidateSkillIsDeleted == False
        )
        skills = [s for s, in self.db.execute(s_stmt).all() if s is not None]
        
        return {
            "candidate_id": candidate_id,
            "first_name": first_name,
            "last_name": last_name,
            "job_profile_id": job_profile_id,
            "total_experience": float(total_exp) if total_exp is not None else None,
            "expected_ctc": float(expected_ctc) if expected_ctc is not None else None,
            "is_active": is_active,
            "status_id": status_id,
            "job_profile": {
                "name": jp_name
            } if jp_name else None,
            "qualifications": qualifications,
            "skills": skills,
            "domains": [domain_id] if domain_id else []
        }
