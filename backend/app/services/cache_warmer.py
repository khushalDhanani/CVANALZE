from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.cache import master_data_cache_manager
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import logger
from app.models.org import OrgCompanyMst, OrgDepartmentMst, OrgJobProfileMst
from app.repositories.job import JobRepository


def _get_db() -> Session | None:
    try:
        if SessionLocal is not None:
            return SessionLocal()
    except Exception as exc:
        logger.warning(f"cache_warmer: Could not create DB session: {exc}")
    return None


def warm_vacancies() -> int:
    db = _get_db()
    if db is None:
        logger.warning("cache_warmer.warm_vacancies: No DB session.")
        return 0
    try:
        jobs = JobRepository.get_all_jobs(db=db)
        count = len(jobs)
        logger.info(f"[WARM] Vacancies refreshed: {count} jobs cached.")
        return count
    except Exception as exc:
        logger.error(f"[WARM] Vacancy refresh failed: {exc}")
        return 0
    finally:
        db.close()


def warm_job_profiles() -> list[dict[str, Any]]:
    db = _get_db()
    if db is None:
        return []
    try:
        stmt = select(OrgJobProfileMst).where(OrgJobProfileMst.JobProfileIsActive == True)
        rows = db.execute(stmt).scalars().all()
        profiles = [
            {
                "id": r.JobProfileID,
                "name": r.JobProfileName,
                "description": r.JobProfileDesc,
                "company_id": r.CompID,
                "department_id": r.DeptID,
                "designation_id": r.DesigID,
            }
            for r in rows
        ]
        master_data_cache_manager.set("job_profiles", profiles)
        logger.info(f"[WARM] Job profiles cached: {len(profiles)}")
        return profiles
    except Exception as exc:
        logger.error(f"[WARM] Job profile refresh failed: {exc}")
        return []
    finally:
        db.close()


def warm_departments() -> list[dict[str, Any]]:
    db = _get_db()
    if db is None:
        return []
    try:
        stmt = select(OrgDepartmentMst).where(OrgDepartmentMst.DeptIsActive == True)
        rows = db.execute(stmt).scalars().all()
        depts = [
            {"id": r.DeptID, "name": r.DeptName, "company_id": r.CompID}
            for r in rows
        ]
        master_data_cache_manager.set("departments", depts)
        logger.info(f"[WARM] Departments cached: {len(depts)}")
        return depts
    except Exception as exc:
        logger.error(f"[WARM] Department refresh failed: {exc}")
        return []
    finally:
        db.close()


def warm_companies() -> list[dict[str, Any]]:
    db = _get_db()
    if db is None:
        return []
    try:
        stmt = select(OrgCompanyMst).where(OrgCompanyMst.CompIsActive == True)
        rows = db.execute(stmt).scalars().all()
        companies = [
            {"id": r.CompID, "name": r.CompName, "business_group_id": r.BusinessGrpID}
            for r in rows
        ]
        master_data_cache_manager.set("companies", companies)
        logger.info(f"[WARM] Companies cached: {len(companies)}")
        return companies
    except Exception as exc:
        logger.error(f"[WARM] Company refresh failed: {exc}")
        return []
    finally:
        db.close()


def warm_skills() -> list[dict[str, Any]]:
    db = _get_db()
    if db is None:
        return []
    try:
        result = db.execute(
            text("SELECT SkillID, SkillTypeID, SkillName, SkillDesc FROM RecruitSkillMst WHERE SkillIsActive = 1")
        )
        skills = [
            {"id": row[0], "type_id": row[1], "name": row[2], "description": row[3]}
            for row in result.fetchall()
        ]
        master_data_cache_manager.set("skills", skills)
        logger.info(f"[WARM] Skills cached: {len(skills)}")
        return skills
    except Exception as exc:
        logger.warning(f"[WARM] Skills refresh failed: {exc}")
        return []
    finally:
        db.close()


def warm_all() -> dict[str, int]:
    counts: dict[str, int] = {}
    try:
        counts["vacancies"] = warm_vacancies()
    except Exception as exc:
        logger.error(f"[WARM] Vacancy refresh failed: {exc}")
    try:
        counts["job_profiles"] = len(warm_job_profiles())
    except Exception as exc:
        logger.error(f"[WARM] Job profile refresh failed: {exc}")
    try:
        counts["departments"] = len(warm_departments())
    except Exception as exc:
        logger.error(f"[WARM] Department refresh failed: {exc}")
    try:
        counts["companies"] = len(warm_companies())
    except Exception as exc:
        logger.error(f"[WARM] Company refresh failed: {exc}")
    try:
        counts["skills"] = len(warm_skills())
    except Exception as exc:
        logger.error(f"[WARM] Skills refresh failed: {exc}")
    logger.info(f"[WARM] All master data refreshed: {counts}")
    return counts


def warm_vacancies_task() -> int:
    return warm_vacancies()


def warm_master_data_task() -> dict[str, int]:
    return warm_all()
