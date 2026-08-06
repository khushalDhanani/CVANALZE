from __future__ import annotations
from sqlalchemy.orm import Session, joinedload
from app.models.recruit import RecruitCandidateMst, RecruitVacancyRequest
from app.models.org import OrgJobProfileMst

def get_candidate_aggregate(db: Session, candidate_id: int) -> dict | None:
    candidate = db.query(RecruitCandidateMst).options(
        joinedload(RecruitCandidateMst.job_profile),
        joinedload(RecruitCandidateMst.qualifications),
        joinedload(RecruitCandidateMst.domains)
    ).filter(RecruitCandidateMst.CandidateID == candidate_id).first()
    
    if not candidate:
        return None
        
    return {
        "candidate_id": candidate.CandidateID,
        "first_name": candidate.CandidateFirstName,
        "last_name": candidate.CandidateLastName,
        "job_profile_id": candidate.CandidateJobProfileID,
        "total_experience": float(candidate.CandidateTotExperience) if candidate.CandidateTotExperience is not None else None,
        "expected_ctc": float(candidate.CandidateExpectedCtc) if candidate.CandidateExpectedCtc is not None else None,
        "is_active": candidate.CandidateIsActive,
        "status_id": candidate.CandidateStatusID,
        "job_profile": {
            "name": candidate.job_profile.JobProfileName if candidate.job_profile else None
        } if candidate.job_profile else None,
        "qualifications": [q.QualID for q in candidate.qualifications],
        "domains": [d.DomainID for d in candidate.domains]
    }

def get_vacancy_aggregate(db: Session, vacancy_id: int) -> dict | None:
    vacancy = db.query(RecruitVacancyRequest).options(
        joinedload(RecruitVacancyRequest.job_profile),
        joinedload(RecruitVacancyRequest.company),
        joinedload(RecruitVacancyRequest.department),
        joinedload(RecruitVacancyRequest.location),
        joinedload(RecruitVacancyRequest.designation),
        joinedload(RecruitVacancyRequest.qualifications),
        joinedload(RecruitVacancyRequest.domains)
    ).filter(RecruitVacancyRequest.VacancyRequestID == vacancy_id).first()
    
    if not vacancy:
        return None
        
    return {
        "vacancy_id": vacancy.VacancyRequestID,
        "job_profile_id": vacancy.JobProfileID,
        "company_id": vacancy.RequestForCompID,
        "department_id": vacancy.RequestForDeptID,
        "location_id": vacancy.RequestForLocationID,
        "designation_id": vacancy.RequestForDesigID,
        "experience_from": float(vacancy.RequestedExperienceRangeFrom) if vacancy.RequestedExperienceRangeFrom is not None else None,
        "experience_to": float(vacancy.RequestedExperienceRangeTo) if vacancy.RequestedExperienceRangeTo is not None else None,
        "ctc_from": float(vacancy.RequestedCTCRangeFrom) if vacancy.RequestedCTCRangeFrom is not None else None,
        "ctc_to": float(vacancy.RequestedCTCRangeTo) if vacancy.RequestedCTCRangeTo is not None else None,
        "additional_knowledge": vacancy.RequestedAdditionalKnowledge,
        "prefered_gender": vacancy.PreferedGender,
        "is_active": vacancy.VacancyRequestIsActive,
        "is_deleted": vacancy.VacancyRequestIsDeleted,
        "is_closed": vacancy.VacancyRequestClose,
        "is_force_closed": vacancy.VacancyRequestIsForceClosed,
        "status_id": vacancy.RequestStatusID,
        "qualifications": [q.QualID for q in vacancy.qualifications],
        "domains": [d.DomainID for d in vacancy.domains]
    }

def get_job_profile_aggregate(db: Session, job_profile_id: int) -> dict | None:
    profile = db.query(OrgJobProfileMst).options(
        joinedload(OrgJobProfileMst.qualifications),
        joinedload(OrgJobProfileMst.domains)
    ).filter(OrgJobProfileMst.JobProfileID == job_profile_id).first()
    
    if not profile:
        return None
        
    return {
        "job_profile_id": profile.JobProfileID,
        "name": profile.JobProfileName,
        "description": profile.JobProfileDesc,
        "company_id": profile.CompID,
        "department_id": profile.DeptID,
        "designation_id": profile.DesigID,
        "is_active": profile.JobProfileIsActive,
        "qualifications": [q.QualID for q in profile.qualifications],
        "domains": [d.DomainID for d in profile.domains]
    }
