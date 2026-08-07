from __future__ import annotations
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import master_data_cache_manager
from app.core.database import MssqlReadSession, PostgresAppSession
from app.core.logging import logger
from app.core.rule_config_manager import RuleConfigManager
from app.models.mssql.organization import OrgCompanyMst, OrgDepartmentMst, OrgJobProfileMst
from app.repositories.job import JobRepository


def _get_db() -> Session | None:
    try:
        if MssqlReadSession is not None:
            return MssqlReadSession()
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


def warm_business_groups() -> list[dict[str, Any]]:
    db = _get_db()
    if db is None:
        return []
    try:
        from app.models.mssql.taxonomy import OrgBusinessGroupMst
        stmt = select(OrgBusinessGroupMst).where(
            (OrgBusinessGroupMst.BusinessGrpIsActive == True) | (OrgBusinessGroupMst.BusinessGrpIsActive.is_(None)),
            (OrgBusinessGroupMst.BusinessGrpIsDeleted == False) | (OrgBusinessGroupMst.BusinessGrpIsDeleted.is_(None)),
        )
        rows = db.execute(stmt).scalars().all()
        groups = [{"id": r.BusinessGrpID, "name": r.BusinessGrpName} for r in rows]
        master_data_cache_manager.set("business_groups", groups)
        logger.info(f"[WARM] Business groups cached: {len(groups)}")
        return groups
    except Exception as exc:
        logger.error(f"[WARM] Business group refresh failed: {exc}")
        return []
    finally:
        db.close()


def warm_locations() -> list[dict[str, Any]]:
    db = _get_db()
    if db is None:
        return []
    try:
        from app.models.mssql.organization import OrgLocationMst
        stmt = select(OrgLocationMst).where(
            (OrgLocationMst.LocIsActive == True) | (OrgLocationMst.LocIsActive.is_(None)),
            (OrgLocationMst.LocIsDeleted == False) | (OrgLocationMst.LocIsDeleted.is_(None)),
        )
        rows = db.execute(stmt).scalars().all()
        locations = [{"id": r.LocID, "name": r.LocName, "company_id": r.CompID, "code": r.LocCode} for r in rows]
        master_data_cache_manager.set("locations", locations)
        logger.info(f"[WARM] Locations cached: {len(locations)}")
        return locations
    except Exception as exc:
        logger.error(f"[WARM] Location refresh failed: {exc}")
        return []
    finally:
        db.close()


def warm_main_departments() -> list[dict[str, Any]]:
    db = _get_db()
    if db is None:
        return []
    try:
        from app.models.mssql.organization import OrgMainDepartmentMst
        stmt = select(OrgMainDepartmentMst).where(
            (OrgMainDepartmentMst.IsActive == True) | (OrgMainDepartmentMst.IsActive.is_(None))
        )
        rows = db.execute(stmt).scalars().all()
        main_depts = [{"id": r.MainDeptID, "name": r.DeptName} for r in rows]
        master_data_cache_manager.set("main_departments", main_depts)
        logger.info(f"[WARM] Main departments cached: {len(main_depts)}")
        return main_depts
    except Exception as exc:
        logger.error(f"[WARM] Main department refresh failed: {exc}")
        return []
    finally:
        db.close()


def warm_departments() -> list[dict[str, Any]]:
    db = _get_db()
    if db is None:
        return []
    try:
        stmt = select(OrgDepartmentMst).where(
            (OrgDepartmentMst.DeptIsActive == True) | (OrgDepartmentMst.DeptIsActive.is_(None)),
            (OrgDepartmentMst.DeptIsDeleted == False) | (OrgDepartmentMst.DeptIsDeleted.is_(None)),
        )
        rows = db.execute(stmt).scalars().all()
        depts = [{"id": r.DeptID, "name": r.DeptName, "company_id": r.CompID, "main_department_id": r.MainDeptID} for r in rows]
        master_data_cache_manager.set("departments", depts)
        logger.info(f"[WARM] Departments cached: {len(depts)}")
        return depts
    except Exception as exc:
        logger.error(f"[WARM] Department refresh failed: {exc}")
        return []
    finally:
        db.close()


def warm_designations() -> list[dict[str, Any]]:
    db = _get_db()
    if db is None:
        return []
    try:
        from app.models.mssql.organization import OrgDesignationMst
        stmt = select(OrgDesignationMst).where(
            (OrgDesignationMst.DesigIsActive == True) | (OrgDesignationMst.DesigIsActive.is_(None)),
            (OrgDesignationMst.DesigIsDeleted == False) | (OrgDesignationMst.DesigIsDeleted.is_(None)),
        )
        rows = db.execute(stmt).scalars().all()
        desigs = [{"id": r.DesigID, "name": r.DesigName, "company_id": r.CompID, "department_id": r.DeptID, "main_department_id": r.MainDeptID} for r in rows]
        master_data_cache_manager.set("designations", desigs)
        logger.info(f"[WARM] Designations cached: {len(desigs)}")
        return desigs
    except Exception as exc:
        logger.error(f"[WARM] Designation refresh failed: {exc}")
        return []
    finally:
        db.close()


def warm_companies() -> list[dict[str, Any]]:
    db = _get_db()
    if db is None:
        return []
    try:
        stmt = select(OrgCompanyMst).where(
            (OrgCompanyMst.CompIsActive == True) | (OrgCompanyMst.CompIsActive.is_(None)),
            (OrgCompanyMst.CompIsDeleted == False) | (OrgCompanyMst.CompIsDeleted.is_(None)),
        )
        rows = db.execute(stmt).scalars().all()
        companies = [{"id": r.CompID, "name": r.CompName, "code": r.CompCode, "business_group_id": r.BusinessGrpID} for r in rows]
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
        from app.models.mssql.taxonomy import RecruitSkillMst
        
        stmt = select(RecruitSkillMst).where(RecruitSkillMst.SkillIsActive == True)
        rows = db.execute(stmt).scalars().all()
        skills = [{"id": r.SkillID, "type_id": r.SkillTypeID, "name": r.SkillName, "description": r.SkillDesc} for r in rows]
        master_data_cache_manager.set("skills", skills)
        logger.info(f"[WARM] Skills cached: {len(skills)}")
        return skills
    except Exception as exc:
        logger.warning(f"[WARM] Skills refresh failed: {exc}")
        return []
    finally:
        db.close()


def warm_department_domains() -> int:
    if PostgresAppSession is None:
        logger.warning("cache_warmer.warm_department_domains: No DB session.")
        return 0
    try:
        from app.repositories.department_domain import department_domain_repository

        department_domain_repository.refresh_cache()
        count = len(department_domain_repository.get_all_domains())
        logger.info(f"[WARM] Department domains refreshed: {count} domains cached.")
        return count
    except Exception as exc:
        logger.error(f"[WARM] Department domain refresh failed: {exc}")
        return 0


def warm_rule_config() -> int:
    """Reload, validate, and atomically swap the rule config from the database."""
    try:
        config = RuleConfigManager.load_config()
        logger.info(f"[WARM] Rule config reloaded: v{config.version}.")
        return 1
    except Exception as exc:
        logger.error(f"[WARM] Rule config reload failed: {exc}")
        return 0


def warm_all() -> dict[str, int]:
    counts: dict[str, int] = {}
    try:
        counts["vacancies"] = warm_vacancies()
    except Exception as exc:
        logger.error(f"[WARM] Vacancy refresh failed: {exc}")
    try:
        counts["business_groups"] = len(warm_business_groups())
    except Exception as exc:
        logger.error(f"[WARM] Business group refresh failed: {exc}")
    try:
        counts["companies"] = len(warm_companies())
    except Exception as exc:
        logger.error(f"[WARM] Company refresh failed: {exc}")
    try:
        counts["locations"] = len(warm_locations())
    except Exception as exc:
        logger.error(f"[WARM] Location refresh failed: {exc}")
    try:
        counts["main_departments"] = len(warm_main_departments())
    except Exception as exc:
        logger.error(f"[WARM] Main department refresh failed: {exc}")
    try:
        counts["departments"] = len(warm_departments())
    except Exception as exc:
        logger.error(f"[WARM] Department refresh failed: {exc}")
    try:
        counts["designations"] = len(warm_designations())
    except Exception as exc:
        logger.error(f"[WARM] Designation refresh failed: {exc}")
    try:
        counts["job_profiles"] = len(warm_job_profiles())
    except Exception as exc:
        logger.error(f"[WARM] Job profile refresh failed: {exc}")
    try:
        counts["skills"] = len(warm_skills())
    except Exception as exc:
        logger.error(f"[WARM] Skills refresh failed: {exc}")
    try:
        counts["department_domains"] = warm_department_domains()
    except Exception as exc:
        logger.error(f"[WARM] Department domain refresh failed: {exc}")
    try:
        counts["rule_config"] = warm_rule_config()
    except Exception as exc:
        logger.error(f"[WARM] Rule config reload failed: {exc}")
    logger.info(f"[WARM] All master data refreshed: {counts}")
    return counts



def warm_vacancies_task() -> int:
    return warm_vacancies()


def warm_master_data_task() -> dict[str, int]:
    return warm_all()
