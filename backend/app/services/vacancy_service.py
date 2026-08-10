from __future__ import annotations
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.mssql.organization import (
    OrgBusinessGroupMst,
    OrgCompanyMst,
    OrgDepartmentMst,
    OrgDesignationMst,
    OrgJobProfileMst,
    OrgLocationMst,
    OrgMainDepartmentMst,
    OrgJobProfileQualificationDet,
)
from app.models.mssql.taxonomy import QualificationMst
from app.models.mssql.vacancy import RecruitVacancyRequest, RecruitVacancyRequriedQualificationDet
from app.schemas.job import JobOpening
from app.services.department_normalizer import DepartmentNormalizer


class VacancyService:
    def __init__(self, db: Session):
        self.db = db

    def get_active_vacancies(self) -> list[JobOpening]:
        """
        Fetch all active, non-closed, non-deleted vacancies with full organization context.
        """
        from sqlalchemy.orm import contains_eager

        stmt = (
            select(RecruitVacancyRequest)
            .join(
                OrgJobProfileMst,
                RecruitVacancyRequest.JobProfileID == OrgJobProfileMst.JobProfileID,
                isouter=True,
            )
            .join(
                OrgDesignationMst,
                RecruitVacancyRequest.RequestForDesigID == OrgDesignationMst.DesigID,
                isouter=True,
            )
            .join(
                OrgCompanyMst,
                RecruitVacancyRequest.RequestForCompID == OrgCompanyMst.CompID,
                isouter=True,
            )
            .join(
                OrgDepartmentMst,
                RecruitVacancyRequest.RequestForDeptID == OrgDepartmentMst.DeptID,
                isouter=True,
            )
            .join(
                OrgLocationMst,
                RecruitVacancyRequest.RequestForLocationID == OrgLocationMst.LocID,
                isouter=True,
            )
            .options(
                contains_eager(RecruitVacancyRequest.job_profile),
                contains_eager(RecruitVacancyRequest.designation),
                contains_eager(RecruitVacancyRequest.company),
                contains_eager(RecruitVacancyRequest.department),
                contains_eager(RecruitVacancyRequest.location),
            )
            .where(
                RecruitVacancyRequest.VacancyRequestIsActive == True,
                or_(
                    RecruitVacancyRequest.VacancyRequestIsDeleted == False,
                    RecruitVacancyRequest.VacancyRequestIsDeleted.is_(None),
                ),
                or_(
                    RecruitVacancyRequest.VacancyRequestClose == False,
                    RecruitVacancyRequest.VacancyRequestClose.is_(None),
                ),
                or_(
                    RecruitVacancyRequest.VacancyRequestIsForceClosed == False,
                    RecruitVacancyRequest.VacancyRequestIsForceClosed.is_(None),
                ),
            )
        )

        results = self.db.execute(stmt).unique().scalars().all()

        biz_groups: dict[int, str] = {}
        try:
            bg_rows = self.db.execute(select(OrgBusinessGroupMst)).scalars().all()
            biz_groups = {bg.BusinessGrpID: bg.BusinessGrpName for bg in bg_rows if bg.BusinessGrpID is not None}
        except Exception as e:
            logger.warning(f"Could not preload OrgBusinessGroupMst: {e}")

        main_depts: dict[int, str] = {}
        try:
            md_rows = self.db.execute(select(OrgMainDepartmentMst)).scalars().all()
            main_depts = {md.MainDeptID: md.DeptName for md in md_rows if md.MainDeptID is not None}
        except Exception as e:
            logger.warning(f"Could not preload OrgMainDepartmentMst: {e}")

        vacancy_qualifications: dict[int, list[str]] = {}
        profile_qualifications: dict[int, list[str]] = {}
        vacancy_ids = [int(vacancy.VacancyRequestID) for vacancy in results if vacancy.VacancyRequestID is not None]
        profile_ids = [int(vacancy.JobProfileID) for vacancy in results if vacancy.JobProfileID is not None]
        try:
            if vacancy_ids:
                qualification_rows = self.db.execute(
                    select(
                        RecruitVacancyRequriedQualificationDet.VacancyRequestID,
                        QualificationMst.QualificationName,
                    )
                    .join(QualificationMst, RecruitVacancyRequriedQualificationDet.RequriedQualificationID == QualificationMst.QualificationID)
                    .where(RecruitVacancyRequriedQualificationDet.VacancyRequestID.in_(vacancy_ids))
                ).all()
                for vacancy_id, qualification_name in qualification_rows:
                    if vacancy_id is not None and qualification_name:
                        vacancy_qualifications.setdefault(int(vacancy_id), []).append(str(qualification_name))
            if profile_ids:
                profile_qualification_rows = self.db.execute(
                    select(
                        OrgJobProfileQualificationDet.JobProfileID,
                        QualificationMst.QualificationName,
                    )
                    .join(QualificationMst, OrgJobProfileQualificationDet.QualificationID == QualificationMst.QualificationID)
                    .where(
                        OrgJobProfileQualificationDet.JobProfileID.in_(profile_ids),
                        or_(
                            OrgJobProfileQualificationDet.QualificationIsDeleted == False,
                            OrgJobProfileQualificationDet.QualificationIsDeleted.is_(None),
                        ),
                    )
                ).all()
                for profile_id, qualification_name in profile_qualification_rows:
                    if profile_id is not None and qualification_name:
                        profile_qualifications.setdefault(int(profile_id), []).append(str(qualification_name))
        except Exception as e:
            logger.warning(f"Could not preload vacancy qualification requirements: {e}")

        job_openings = []
        for vacancy in results:
            qualifications = vacancy_qualifications.get(int(vacancy.VacancyRequestID), [])
            if not qualifications and vacancy.JobProfileID is not None:
                qualifications = profile_qualifications.get(int(vacancy.JobProfileID), [])
            job_openings.append(self.map_to_job_requirement(vacancy, biz_groups=biz_groups, main_depts=main_depts, qualifications=qualifications))

        unique_dept_ids = sorted({j.department_id for j in job_openings if j.department_id is not None})
        logger.info(f"Active Vacancies: {len(job_openings)} | Departments: {len(unique_dept_ids)} | Department IDs: {unique_dept_ids}")
        return job_openings

    def map_to_job_requirement(
        self,
        vacancy: RecruitVacancyRequest,
        biz_groups: dict[int, str] | None = None,
        main_depts: dict[int, str] | None = None,
        qualifications: list[str] | None = None,
    ) -> JobOpening:
        # Determine title dynamically: JobProfile -> Designation -> Fallback
        if vacancy.job_profile and vacancy.job_profile.JobProfileName:
            title = vacancy.job_profile.JobProfileName
        elif vacancy.designation and vacancy.designation.DesigName:
            title = vacancy.designation.DesigName
        else:
            title = f"Vacancy #{vacancy.VacancyRequestID}"

        # Extract skills/keywords from Additional Knowledge (filtering garbage placeholders)
        GARBAGE_SKILLS = {
            "-",
            ".",
            "yes",
            "no",
            "n/a",
            "na",
            "nil",
            "none",
            "test",
            "1",
            "0",
            "ok",
            "good",
        }
        skills = []
        if vacancy.RequestedAdditionalKnowledge:
            raw_skills = [s.strip() for s in vacancy.RequestedAdditionalKnowledge.split(",") if s.strip()]
            skills = [s for s in raw_skills if len(s) > 1 and s.lower() not in GARBAGE_SKILLS]

        dept_name = vacancy.department.DeptName if vacancy.department else "Unknown Department"
        comp_name = vacancy.company.CompName if vacancy.company else "Unknown Company"
        loc_name = vacancy.location.LocName if vacancy.location else "Unknown Location"
        desig_name = vacancy.designation.DesigName if vacancy.designation else None

        dept_id = vacancy.RequestForDeptID
        if dept_id is None and vacancy.job_profile:
            dept_id = vacancy.job_profile.DeptID

        desig_id = vacancy.RequestForDesigID
        if desig_id is None and vacancy.job_profile:
            desig_id = vacancy.job_profile.DesigID

        # Hierarchy resolution for Business Group & Main Department
        biz_group_id = vacancy.company.BusinessGrpID if vacancy.company else None
        biz_group_name = None
        if biz_group_id is not None:
            if biz_groups is not None:
                biz_group_name = biz_groups.get(biz_group_id)
            else:
                biz_grp = self.db.scalar(select(OrgBusinessGroupMst).where(OrgBusinessGroupMst.BusinessGrpID == biz_group_id))
                if biz_grp:
                    biz_group_name = biz_grp.BusinessGrpName

        main_dept_id = vacancy.RequestForMainDeptID
        if main_dept_id is None and vacancy.department:
            main_dept_id = vacancy.department.MainDeptID
        if main_dept_id is None and vacancy.job_profile:
            main_dept_id = vacancy.job_profile.MainDeptID

        main_dept_name = None
        if main_dept_id is not None:
            if main_depts is not None:
                main_dept_name = main_depts.get(main_dept_id)
            else:
                main_dept = self.db.scalar(select(OrgMainDepartmentMst).where(OrgMainDepartmentMst.MainDeptID == main_dept_id))
                if main_dept:
                    main_dept_name = main_dept.DeptName

        # Convert Decimals to float safely
        def _safe_float_db(val: Any) -> float | None:
            if val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        min_exp = _safe_float_db(vacancy.RequestedExperienceRangeFrom)
        max_exp = _safe_float_db(vacancy.RequestedExperienceRangeTo)
        min_ctc = _safe_float_db(vacancy.RequestedCTCRangeFrom)
        max_ctc = _safe_float_db(vacancy.RequestedCTCRangeTo)

        # Config Validation Warning
        if not skills and min_exp is None and not vacancy.job_profile:
            logger.warning(
                f"CONFIG WARNING: Vacancy {vacancy.VacancyRequestID} ('{title}') has no explicit skills, "
                f"experience requirements, or detailed job profile. Matches will rely only on title/domain and may be low-confidence."
            )

        job_desc = vacancy.job_profile.JobProfileDesc if vacancy.job_profile and vacancy.job_profile.JobProfileDesc else None

        industry_dept_result = DepartmentNormalizer.normalize_department(dept_name)
        industry_title_result = DepartmentNormalizer.normalize_designation(title)

        return JobOpening(
            id=str(vacancy.VacancyRequestID),
            title=title,
            department=dept_name,
            job_description=job_desc,
            responsibilities=job_desc,
            required_skills=skills,
            required_skills_are_mandatory=True,
            preferred_keywords=[],
            min_experience_years=min_exp,
            max_experience_years=max_exp,
            min_ctc=min_ctc,
            max_ctc=max_ctc,
            education=" / ".join(dict.fromkeys(qualifications or [])) or None,
            preferred_gender=vacancy.PreferedGender,
            company_name=comp_name,
            location_name=loc_name,
            vacancy_id=vacancy.VacancyRequestID,
            job_profile_id=vacancy.JobProfileID,
            business_group_id=biz_group_id,
            business_group_name=biz_group_name,
            company_id=vacancy.RequestForCompID,
            company_name_db=comp_name,
            location_id=vacancy.RequestForLocationID,
            location_name_db=loc_name,
            main_department_id=main_dept_id,
            main_department_name=main_dept_name,
            department_id=dept_id,
            department_name=dept_name,
            designation_id=desig_id,
            designation_name=desig_name,
            industry_title=industry_title_result.get("industry_designation"),
            industry_department=industry_dept_result.get("industry_department"),
        )
