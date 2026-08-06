from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.mssql.vacancy import (
    RecruitVacancyRequest,
    RecruitVacancyRequriedQualificationDet,
    RecruitVacancyRequestTrack,
    RecruitVacancyCandidateList,
    RecruitVacancyCandidiateHistoryDet
)
from app.models.mssql.organization import OrgJobProfileMst, JobProfileDomainKnowledgeDet
from app.models.mssql.taxonomy import QualificationMst, TransactionStatusMst, RecruitDomainKnowledgeMst
from app.models.mssql.candidate import RecruitCandidateMst


class VacancySourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_vacancy_aggregate(self, vacancy_id: int) -> dict | None:
        stmt = (
            select(
                RecruitVacancyRequest.VacancyRequestID,
                RecruitVacancyRequest.JobProfileID,
                OrgJobProfileMst.JobProfileName,
                RecruitVacancyRequest.RequestForCompID,
                RecruitVacancyRequest.RequestForDeptID,
                RecruitVacancyRequest.RequestForLocationID,
                RecruitVacancyRequest.RequestForDesigID,
                RecruitVacancyRequest.RequestedExperienceRangeFrom,
                RecruitVacancyRequest.RequestedExperienceRangeTo,
                RecruitVacancyRequest.RequestedCTCRangeFrom,
                RecruitVacancyRequest.RequestedCTCRangeTo,
                RecruitVacancyRequest.RequestedAdditionalKnowledge,
                RecruitVacancyRequest.PreferedGender,
                RecruitVacancyRequest.VacancyRequestIsActive,
                RecruitVacancyRequest.VacancyRequestIsDeleted,
                RecruitVacancyRequest.VacancyRequestClose,
                RecruitVacancyRequest.VacancyRequestIsForceClosed,
                RecruitVacancyRequest.RequestStatusID,
                TransactionStatusMst.StatusDesc
            )
            .outerjoin(
                OrgJobProfileMst, RecruitVacancyRequest.JobProfileID == OrgJobProfileMst.JobProfileID
            )
            .outerjoin(
                TransactionStatusMst, RecruitVacancyRequest.RequestStatusID == TransactionStatusMst.StatusID
            )
            .where(RecruitVacancyRequest.VacancyRequestID == vacancy_id)
        )
        row = self.db.execute(stmt).first()
        if not row:
            return None
            
        (
            v_id, jp_id, jp_name, comp_id, dept_id, loc_id, desig_id,
            exp_from, exp_to, ctc_from, ctc_to,
            add_know, gender, is_active, is_deleted, is_closed,
            is_force_closed, status_id, status_name
        ) = row

        # Required Qualifications
        q_stmt = select(
            RecruitVacancyRequriedQualificationDet.RequriedQualificationID,
            QualificationMst.QualificationName
        ).outerjoin(
            QualificationMst, RecruitVacancyRequriedQualificationDet.RequriedQualificationID == QualificationMst.QualificationID
        ).where(
            RecruitVacancyRequriedQualificationDet.VacancyRequestID == vacancy_id
        )
        qualifications = [
            {"qualification_id": r.RequriedQualificationID, "name": r.QualificationName}
            for r in self.db.execute(q_stmt).all() if r.RequriedQualificationID is not None
        ]

        # Job Profile Domains
        domains = []
        if jp_id:
            d_stmt = select(
                JobProfileDomainKnowledgeDet.DomainKnowlgID,
                RecruitDomainKnowledgeMst.DomainKnowlgName
            ).outerjoin(
                RecruitDomainKnowledgeMst, JobProfileDomainKnowledgeDet.DomainKnowlgID == RecruitDomainKnowledgeMst.DomainKnowlgID
            ).where(
                JobProfileDomainKnowledgeDet.JobProfileID == jp_id,
                JobProfileDomainKnowledgeDet.JobProfileDomainKnowledgeDetIsActive == True
            )
            domains = [
                {"domain_id": r.DomainKnowlgID, "name": r.DomainKnowlgName}
                for r in self.db.execute(d_stmt).all() if r.DomainKnowlgID is not None
            ]

        # Request Tracking
        track_stmt = select(
            RecruitVacancyRequestTrack.VacancyTrackID,
            RecruitVacancyRequestTrack.VacancyReqStatusID,
            TransactionStatusMst.StatusDesc,
            RecruitVacancyRequestTrack.VacancyReqRemark
        ).outerjoin(
            TransactionStatusMst, RecruitVacancyRequestTrack.VacancyReqStatusID == TransactionStatusMst.StatusID
        ).where(
            RecruitVacancyRequestTrack.VacancyRequestID == vacancy_id,
            RecruitVacancyRequestTrack.VacancyReqIsDeleted == False
        )
        request_track = [
            {
                "track_id": r.VacancyTrackID,
                "status_id": r.VacancyReqStatusID,
                "status_name": r.StatusDesc,
                "remark": r.VacancyReqRemark
            }
            for r in self.db.execute(track_stmt).all()
        ]

        # Candidate Applications
        cand_stmt = select(
            RecruitVacancyCandidateList.VacancyCandidateID,
            RecruitVacancyCandidateList.CandidateID,
            RecruitCandidateMst.CandidateFirstName,
            RecruitCandidateMst.CandidateLastName,
            RecruitVacancyCandidateList.StatusID,
            TransactionStatusMst.StatusDesc,
            RecruitVacancyCandidateList.HRRemarks
        ).outerjoin(
            RecruitCandidateMst, RecruitVacancyCandidateList.CandidateID == RecruitCandidateMst.CandidateID
        ).outerjoin(
            TransactionStatusMst, RecruitVacancyCandidateList.StatusID == TransactionStatusMst.StatusID
        ).where(
            RecruitVacancyCandidateList.VacancyRequestID == vacancy_id
        )
        applications = [
            {
                "application_id": r.VacancyCandidateID,
                "candidate_id": r.CandidateID,
                "candidate_first_name": r.CandidateFirstName,
                "candidate_last_name": r.CandidateLastName,
                "status_id": r.StatusID,
                "status_name": r.StatusDesc,
                "hr_remarks": r.HRRemarks
            }
            for r in self.db.execute(cand_stmt).all()
        ]

        # Candidate History
        history_stmt = select(
            RecruitVacancyCandidiateHistoryDet.VacancyAppliedHistoryID,
            RecruitVacancyCandidiateHistoryDet.VacancyCandidateID,
            RecruitVacancyCandidiateHistoryDet.StatusID,
            TransactionStatusMst.StatusDesc,
            RecruitVacancyCandidiateHistoryDet.StatusDT
        ).join(
            RecruitVacancyCandidateList,
            RecruitVacancyCandidiateHistoryDet.VacancyCandidateID == RecruitVacancyCandidateList.VacancyCandidateID
        ).outerjoin(
            TransactionStatusMst, RecruitVacancyCandidiateHistoryDet.StatusID == TransactionStatusMst.StatusID
        ).where(
            RecruitVacancyCandidateList.VacancyRequestID == vacancy_id
        )
        candidate_history = [
            {
                "history_id": r.VacancyAppliedHistoryID,
                "application_id": r.VacancyCandidateID,
                "status_id": r.StatusID,
                "status_name": r.StatusDesc,
                "status_date": str(r.StatusDT) if r.StatusDT else None
            }
            for r in self.db.execute(history_stmt).all()
        ]

        return {
            "vacancy_id": v_id,
            "company_id": comp_id,
            "department_id": dept_id,
            "location_id": loc_id,
            "designation_id": desig_id,
            "experience_from": float(exp_from) if exp_from is not None else None,
            "experience_to": float(exp_to) if exp_to is not None else None,
            "ctc_from": float(ctc_from) if ctc_from is not None else None,
            "ctc_to": float(ctc_to) if ctc_to is not None else None,
            "additional_knowledge": add_know,
            "prefered_gender": gender,
            "is_active": is_active,
            "is_deleted": is_deleted,
            "is_closed": is_closed,
            "is_force_closed": is_force_closed,
            "status": {
                "id": status_id,
                "name": status_name
            } if status_id else None,
            "job_profile": {
                "id": jp_id,
                "name": jp_name,
                "domains": domains
            } if jp_id else None,
            "required_qualifications": qualifications,
            "request_track": request_track,
            "candidate_applications": applications,
            "candidate_history": candidate_history
        }
