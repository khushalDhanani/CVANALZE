from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.mssql.vacancy import (
    RecruitVacancyRequest,
    RecruitVacancyRequriedQualificationDet,
)

class VacancySourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_vacancy_aggregate(self, vacancy_id: int) -> dict | None:
        stmt = (
            select(
                RecruitVacancyRequest.VacancyRequestID,
                RecruitVacancyRequest.JobProfileID,
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
                RecruitVacancyRequest.RequestStatusID
            )
            .where(RecruitVacancyRequest.VacancyRequestID == vacancy_id)
        )
        row = self.db.execute(stmt).first()
        if not row:
            return None
            
        (
            v_id, jp_id, comp_id, dept_id, loc_id, desig_id,
            exp_from, exp_to, ctc_from, ctc_to,
            add_know, gender, is_active, is_deleted, is_closed,
            is_force_closed, status_id
        ) = row

        q_stmt = select(RecruitVacancyRequriedQualificationDet.QualificationID).where(
            RecruitVacancyRequriedQualificationDet.VacancyRequestID == vacancy_id,
            RecruitVacancyRequriedQualificationDet.VacancyReqQualiIsActive == True,
            RecruitVacancyRequriedQualificationDet.VacancyReqQualiIsDeleted == False
        )
        qualifications = [q for q, in self.db.execute(q_stmt).all() if q is not None]

        return {
            "vacancy_id": v_id,
            "job_profile_id": jp_id,
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
            "status_id": status_id,
            "qualifications": qualifications,
            "domains": []
        }
