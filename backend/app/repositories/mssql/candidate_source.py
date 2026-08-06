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
from app.models.mssql.organization import OrgJobProfileMst, OrgLocationMst
from app.models.mssql.taxonomy import RecruitSkillMst, LanguageMst, RecruitDomainKnowledgeMst


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
                RecruitCandidateMst.CandidateDomainKnowlgID,
                RecruitDomainKnowledgeMst.DomainKnowlgName,
                RecruitCandidateMst.NoticePeriodID,
                RecruitCandidateNoticePeriodMst.NoticePeriod
            )
            .outerjoin(
                OrgJobProfileMst,
                RecruitCandidateMst.CandidateJobProfileID == OrgJobProfileMst.JobProfileID
            )
            .outerjoin(
                RecruitDomainKnowledgeMst,
                RecruitCandidateMst.CandidateDomainKnowlgID == RecruitDomainKnowledgeMst.DomainKnowlgID
            )
            .outerjoin(
                RecruitCandidateNoticePeriodMst,
                RecruitCandidateMst.NoticePeriodID == RecruitCandidateNoticePeriodMst.NoticePeriodID
            )
            .where(RecruitCandidateMst.CandidateID == candidate_id)
        )
        row = self.db.execute(stmt).first()
        if not row:
            return None
            
        (
            c_id, first_name, last_name, job_profile_id, total_exp,
            expected_ctc, is_active, status_id, jp_name, domain_id,
            domain_name, np_id, np_name
        ) = row

        # Qualifications
        q_stmt = select(
            RecruitCandidateQualificationDet.QualificationID,
            RecruitCandidateQualificationDet.CollegeName,
            RecruitCandidateQualificationDet.UniversityName,
            RecruitCandidateQualificationDet.PassingYear,
            RecruitCandidateQualificationDet.PassPercentage,
            RecruitCandidateQualificationDet.CourseType,
            RecruitCandidateQualificationDet.Pursuing
        ).where(
            RecruitCandidateQualificationDet.CandidateID == candidate_id,
            RecruitCandidateQualificationDet.CandidQualiIsActive == True,
            RecruitCandidateQualificationDet.CandidQualiIsDeleted == False
        )
        qualifications = [
            {
                "qualification_id": r.QualificationID,
                "college": r.CollegeName,
                "university": r.UniversityName,
                "passing_year": r.PassingYear,
                "percentage": float(r.PassPercentage) if r.PassPercentage is not None else None,
                "course_type": r.CourseType,
                "is_pursuing": r.Pursuing
            }
            for r in self.db.execute(q_stmt).all()
        ]

        # Skills
        s_stmt = select(
            RecruitCandidateSkillDet.SkillID,
            RecruitSkillMst.SkillName
        ).outerjoin(
            RecruitSkillMst, RecruitCandidateSkillDet.SkillID == RecruitSkillMst.SkillID
        ).where(
            RecruitCandidateSkillDet.CandidateID == candidate_id,
            RecruitCandidateSkillDet.IsActive == True
        )
        skills = [
            {
                "skill_id": r.SkillID,
                "name": r.SkillName
            }
            for r in self.db.execute(s_stmt).all() if r.SkillID is not None
        ]
        
        # Experiences
        e_stmt = select(
            RecruitCandidateExperienceDet.CandidExpDetID,
            RecruitCandidateExperienceDet.PrevOrganizationName,
            RecruitCandidateExperienceDet.PrevDesignation,
            RecruitCandidateExperienceDet.PrevCtc,
            RecruitCandidateExperienceDet.IsCurrentlyWorking,
            RecruitCandidateExperienceDet.PrevDurectionFrom,
            RecruitCandidateExperienceDet.PrevDurectionTo
        ).where(
            RecruitCandidateExperienceDet.CandidateID == candidate_id,
            RecruitCandidateExperienceDet.CandidExpIsActive == True,
            RecruitCandidateExperienceDet.CandidExpIsDeleted == False
        )
        experiences = [
            {
                "experience_id": r.CandidExpDetID,
                "organization": r.PrevOrganizationName,
                "designation": r.PrevDesignation,
                "ctc": float(r.PrevCtc) if r.PrevCtc is not None else None,
                "is_current": r.IsCurrentlyWorking,
                "from_date": str(r.PrevDurectionFrom) if r.PrevDurectionFrom else None,
                "to_date": str(r.PrevDurectionTo) if r.PrevDurectionTo else None
            }
            for r in self.db.execute(e_stmt).all()
        ]

        # Languages
        l_stmt = select(
            RecruitCandidateLanguageDet.LanguageID,
            LanguageMst.LanguageDesc,
            RecruitCandidateLanguageDet.LanguageRead,
            RecruitCandidateLanguageDet.LanguageWrite,
            RecruitCandidateLanguageDet.LanguageSpeak
        ).outerjoin(
            LanguageMst, RecruitCandidateLanguageDet.LanguageID == LanguageMst.LanguageID
        ).where(
            RecruitCandidateLanguageDet.CandidateID == candidate_id,
            RecruitCandidateLanguageDet.LanguageIsDeleted == False
        )
        languages = [
            {
                "language_id": r.LanguageID,
                "name": r.LanguageDesc,
                "read": r.LanguageRead,
                "write": r.LanguageWrite,
                "speak": r.LanguageSpeak
            }
            for r in self.db.execute(l_stmt).all() if r.LanguageID is not None
        ]

        # Locations
        loc_stmt = select(
            RecruitCandidateLocationMst.LocID,
            OrgLocationMst.LocName
        ).outerjoin(
            OrgLocationMst, RecruitCandidateLocationMst.LocID == OrgLocationMst.LocID
        ).where(
            RecruitCandidateLocationMst.CandidateID == candidate_id,
            RecruitCandidateLocationMst.IsActive == True
        )
        locations = [
            {
                "location_id": r.LocID,
                "name": r.LocName
            }
            for r in self.db.execute(loc_stmt).all() if r.LocID is not None
        ]

        return {
            "candidate_id": c_id,
            "first_name": first_name,
            "last_name": last_name,
            "job_profile_id": job_profile_id,
            "total_experience": float(total_exp) if total_exp is not None else None,
            "expected_ctc": float(expected_ctc) if expected_ctc is not None else None,
            "is_active": is_active,
            "status_id": status_id,
            "job_profile": {
                "id": job_profile_id,
                "name": jp_name
            } if job_profile_id else None,
            "qualifications": qualifications,
            "skills": skills,
            "experiences": experiences,
            "languages": languages,
            "locations": locations,
            "notice_period": {
                "id": np_id,
                "name": np_name
            } if np_id else None,
            "domain_knowledge": {
                "id": domain_id,
                "name": domain_name
            } if domain_id else None
        }
