from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.recruit import RecruitVacancyRequest
from app.models.org import OrgJobProfileMst, OrgDepartmentMst, OrgCompanyMst, OrgLocationMst, OrgDesignationMst
from app.schemas.job import JobOpening

class VacancyService:
    def __init__(self, db: Session):
        self.db = db

    def get_active_vacancies(self) -> list[JobOpening]:
        """
        Fetch all active, non-closed, non-deleted vacancies with full organization context.
        """
        stmt = (
            select(RecruitVacancyRequest)
            .join(OrgJobProfileMst, RecruitVacancyRequest.JobProfileID == OrgJobProfileMst.JobProfileID, isouter=True)
            .join(OrgDesignationMst, RecruitVacancyRequest.RequestForDesigID == OrgDesignationMst.DesigID, isouter=True)
            .join(OrgCompanyMst, RecruitVacancyRequest.RequestForCompID == OrgCompanyMst.CompID, isouter=True)
            .join(OrgDepartmentMst, RecruitVacancyRequest.RequestForDeptID == OrgDepartmentMst.DeptID, isouter=True)
            .join(OrgLocationMst, RecruitVacancyRequest.RequestForLocationID == OrgLocationMst.LocID, isouter=True)
            .where(
                RecruitVacancyRequest.VacancyRequestIsActive == True,
                or_(RecruitVacancyRequest.VacancyRequestIsDeleted == False, RecruitVacancyRequest.VacancyRequestIsDeleted.is_(None)),
                or_(RecruitVacancyRequest.VacancyRequestClose == False, RecruitVacancyRequest.VacancyRequestClose.is_(None)),
                or_(RecruitVacancyRequest.VacancyRequestIsForceClosed == False, RecruitVacancyRequest.VacancyRequestIsForceClosed.is_(None))
            )
        )
        
        results = self.db.execute(stmt).scalars().all()
        
        job_openings = []
        for vacancy in results:
            job_openings.append(self.map_to_job_requirement(vacancy))
            
        unique_dept_ids = sorted(list({j.department_id for j in job_openings if j.department_id is not None}))
        logger.info(
            f"Active Vacancies: {len(job_openings)} | Departments: {len(unique_dept_ids)} | Department IDs: {unique_dept_ids}"
        )
        return job_openings

    def map_to_job_requirement(self, vacancy: RecruitVacancyRequest) -> JobOpening:
        # Determine title dynamically: JobProfile -> Designation -> Fallback
        if vacancy.job_profile and vacancy.job_profile.JobProfileName:
            title = vacancy.job_profile.JobProfileName
        elif vacancy.designation and vacancy.designation.DesigName:
            title = vacancy.designation.DesigName
        else:
            title = f"Vacancy #{vacancy.VacancyRequestID}"
        
        # Extract skills/keywords from Additional Knowledge (filtering garbage placeholders)
        GARBAGE_SKILLS = {"-", ".", "yes", "no", "n/a", "na", "nil", "none", "test", "1", "0", "ok", "good"}
        skills = []
        if vacancy.RequestedAdditionalKnowledge:
            raw_skills = [s.strip() for s in vacancy.RequestedAdditionalKnowledge.split(",") if s.strip()]
            skills = [
                s for s in raw_skills
                if len(s) > 1 and s.lower() not in GARBAGE_SKILLS
            ]
            
        dept_name = vacancy.department.DeptName if vacancy.department else "Unknown Department"
        comp_name = vacancy.company.CompName if vacancy.company else "Unknown Company"
        loc_name = vacancy.location.LocName if vacancy.location else "Unknown Location"
        
        dept_id = vacancy.RequestForDeptID
        if dept_id is None and vacancy.job_profile:
            dept_id = vacancy.job_profile.DeptID

        # Convert Decimals to float
        min_exp = float(vacancy.RequestedExperienceRangeFrom) if vacancy.RequestedExperienceRangeFrom is not None else None
        max_exp = float(vacancy.RequestedExperienceRangeTo) if vacancy.RequestedExperienceRangeTo is not None else None
        min_ctc = float(vacancy.RequestedCTCRangeFrom) if vacancy.RequestedCTCRangeFrom is not None else None
        max_ctc = float(vacancy.RequestedCTCRangeTo) if vacancy.RequestedCTCRangeTo is not None else None
        
        # Config Validation Warning
        if not skills and min_exp is None and not vacancy.job_profile:
            logger.warning(
                f"CONFIG WARNING: Vacancy {vacancy.VacancyRequestID} ('{title}') has no explicit skills, "
                f"experience requirements, or detailed job profile. Matches will rely only on title/domain and may be low-confidence."
            )
        
        
        job_desc = vacancy.job_profile.JobProfileDesc if vacancy.job_profile and vacancy.job_profile.JobProfileDesc else None

        return JobOpening(
            id=str(vacancy.VacancyRequestID),
            title=title,
            department=dept_name,
            job_description=job_desc,
            responsibilities=job_desc,
            required_skills=skills,
            preferred_keywords=skills, # Just mapping same for now
            min_experience_years=min_exp,
            max_experience_years=max_exp,
            min_ctc=min_ctc,
            max_ctc=max_ctc,
            preferred_gender=vacancy.PreferedGender,
            company_name=comp_name,
            location_name=loc_name,
            vacancy_id=vacancy.VacancyRequestID,
            job_profile_id=vacancy.JobProfileID,
            company_id=vacancy.RequestForCompID,
            department_id=dept_id,
            department_name=dept_name,
            location_id=vacancy.RequestForLocationID
        )

