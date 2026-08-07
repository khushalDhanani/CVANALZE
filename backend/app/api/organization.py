from __future__ import annotations
from typing import Any, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.database import MssqlReadSession
from app.repositories.mssql.organization_source import OrganizationSourceRepository
from app.core.cache import master_data_cache_manager

router = APIRouter(prefix="/organization", tags=["Organization Hierarchy"])


class HierarchyValidationRequest(BaseModel):
    business_group_id: Optional[int] = Field(None, description="Business Group ID")
    company_id: Optional[int] = Field(None, description="Company ID")
    location_id: Optional[int] = Field(None, description="Location ID")
    main_department_id: Optional[int] = Field(None, description="Main Department ID")
    department_id: Optional[int] = Field(None, description="Department ID")
    designation_id: Optional[int] = Field(None, description="Designation ID")


@router.get("/business-groups")
def get_business_groups():
    """Fetch all active business groups."""
    cached = master_data_cache_manager.get("business_groups")
    if cached:
        return cached

    if MssqlReadSession is None:
        return []
    with MssqlReadSession() as db:
        repo = OrganizationSourceRepository(db)
        groups = repo.get_business_groups()
        return [{"id": g.BusinessGrpID, "name": g.BusinessGrpName} for g in groups]


@router.get("/companies")
def get_companies(business_group_id: Optional[int] = Query(None)):
    """Fetch active companies, optionally filtered by business_group_id."""
    if business_group_id is None:
        cached = master_data_cache_manager.get("companies")
        if cached:
            return cached

    if MssqlReadSession is None:
        return []
    with MssqlReadSession() as db:
        repo = OrganizationSourceRepository(db)
        comps = repo.get_companies(business_group_id=business_group_id)
        return [{"id": c.CompID, "name": c.CompName, "code": c.CompCode, "business_group_id": c.BusinessGrpID} for c in comps]


@router.get("/locations")
def get_locations(company_id: Optional[int] = Query(None)):
    """Fetch active locations, optionally filtered by company_id."""
    if company_id is None:
        cached = master_data_cache_manager.get("locations")
        if cached:
            return cached

    if MssqlReadSession is None:
        return []
    with MssqlReadSession() as db:
        repo = OrganizationSourceRepository(db)
        locs = repo.get_locations(company_id=company_id)
        return [{"id": l.LocID, "name": l.LocName, "code": l.LocCode, "company_id": l.CompID} for l in locs]


@router.get("/main-departments")
def get_main_departments():
    """Fetch active main departments."""
    cached = master_data_cache_manager.get("main_departments")
    if cached:
        return cached

    if MssqlReadSession is None:
        return []
    with MssqlReadSession() as db:
        repo = OrganizationSourceRepository(db)
        main_depts = repo.get_main_departments()
        return [{"id": md.MainDeptID, "name": md.DeptName} for md in main_depts]


@router.get("/departments")
def get_departments(
    company_id: Optional[int] = Query(None),
    main_department_id: Optional[int] = Query(None),
):
    """Fetch active departments, optionally filtered by company_id or main_department_id."""
    if company_id is None and main_department_id is None:
        cached = master_data_cache_manager.get("departments")
        if cached:
            return cached

    if MssqlReadSession is None:
        return []
    with MssqlReadSession() as db:
        repo = OrganizationSourceRepository(db)
        depts = repo.get_active_departments(company_id=company_id, main_dept_id=main_department_id)
        return [
            {
                "id": d.DeptID,
                "name": d.DeptName,
                "company_id": d.CompID,
                "main_department_id": d.MainDeptID,
            }
            for d in depts
        ]


@router.get("/designations")
def get_designations(
    company_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    main_department_id: Optional[int] = Query(None),
):
    """Fetch active designations, optionally filtered by company_id, department_id, or main_department_id."""
    if company_id is None and department_id is None and main_department_id is None:
        cached = master_data_cache_manager.get("designations")
        if cached:
            return cached

    if MssqlReadSession is None:
        return []
    with MssqlReadSession() as db:
        repo = OrganizationSourceRepository(db)
        desigs = repo.get_all_designations(
            company_id=company_id, dept_id=department_id, main_dept_id=main_department_id
        )
        return [
            {
                "id": ds.DesigID,
                "name": ds.DesigName,
                "company_id": ds.CompID,
                "department_id": ds.DeptID,
                "main_department_id": ds.MainDeptID,
            }
            for ds in desigs
        ]


@router.get("/hierarchy")
def get_hierarchy():
    """Fetch the complete cascading hierarchy options map."""
    b_groups = get_business_groups()
    comps = get_companies()
    locs = get_locations()
    m_depts = get_main_departments()
    depts = get_departments()
    desigs = get_designations()

    return {
        "business_groups": b_groups,
        "companies": comps,
        "locations": locs,
        "main_departments": m_depts,
        "departments": depts,
        "designations": desigs,
    }


@router.post("/validate")
def validate_hierarchy(payload: HierarchyValidationRequest):
    """Validates whether a selected combination of parent-child hierarchy IDs is valid."""
    if MssqlReadSession is None:
        return {"is_valid": True, "errors": [], "details": {"note": "MSSQL Session unavailable; bypassed."}}

    with MssqlReadSession() as db:
        repo = OrganizationSourceRepository(db)
        return repo.validate_hierarchy(
            business_group_id=payload.business_group_id,
            company_id=payload.company_id,
            location_id=payload.location_id,
            main_dept_id=payload.main_department_id,
            dept_id=payload.department_id,
            desig_id=payload.designation_id,
        )
