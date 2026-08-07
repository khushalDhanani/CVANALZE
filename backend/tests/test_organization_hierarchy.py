from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from app.models.mssql.organization import (
    OrgBusinessGroupMst,
    OrgCompanyMst,
    OrgLocationMst,
    OrgMainDepartmentMst,
    OrgDepartmentMst,
    OrgDesignationMst,
)
from app.repositories.mssql.organization_source import OrganizationSourceRepository


def create_mock_db():
    db = MagicMock()

    bg1 = OrgBusinessGroupMst(BusinessGrpID=1, BusinessGrpName="Aether Group", BusinessGrpIsActive=True)
    comp1 = OrgCompanyMst(CompID=10, BusinessGrpID=1, CompName="Aether Chem", CompIsActive=True)
    comp2 = OrgCompanyMst(CompID=20, BusinessGrpID=2, CompName="Other Corp", CompIsActive=True)
    loc1 = OrgLocationMst(LocID=100, CompID=10, LocName="Surat Plant", LocIsActive=True)
    main_dept1 = OrgMainDepartmentMst(MainDeptID=5, DeptName="Manufacturing", IsActive=True)
    dept1 = OrgDepartmentMst(DeptID=50, CompID=10, MainDeptID=5, DeptName="Production", DeptIsActive=True)
    desig1 = OrgDesignationMst(DesigID=500, CompID=10, DeptID=50, MainDeptID=5, DesigName="Plant Chemist", DesigIsActive=True)

    def scalar_mock(stmt):
        stmt_str = str(stmt).lower()
        if "orgcompanymst" in stmt_str:
            if "10" in stmt_str:
                return comp1
            if "20" in stmt_str:
                return comp2
            return comp1
        if "orglocationmst" in stmt_str:
            return loc1
        if "orgdepartmentmst" in stmt_str:
            return dept1
        if "orgdesignationmst" in stmt_str:
            return desig1
        return None

    db.scalar.side_effect = scalar_mock
    return db


def test_hierarchy_validation_valid():
    db = create_mock_db()
    repo = OrganizationSourceRepository(db)

    res = repo.validate_hierarchy(
        business_group_id=1,
        company_id=10,
        location_id=100,
        main_dept_id=5,
        dept_id=50,
        desig_id=500,
    )

    assert res["is_valid"] is True
    assert res["errors"] == []
    assert res["details"]["company_name"] == "Aether Chem"


def test_hierarchy_validation_invalid_company_bg_mismatch():
    db = create_mock_db()
    repo = OrganizationSourceRepository(db)

    res = repo.validate_hierarchy(
        business_group_id=99,  # Mismatched Business Group ID
        company_id=10,
    )

    assert res["is_valid"] is False
    assert len(res["errors"]) == 1
    assert "belongs to Business Group 1, not 99" in res["errors"][0]


def test_hierarchy_validation_invalid_location_company_mismatch():
    db = create_mock_db()
    repo = OrganizationSourceRepository(db)

    res = repo.validate_hierarchy(
        company_id=999,  # Mismatched Company ID for Location (which has CompID=10)
        location_id=100,
    )

    assert res["is_valid"] is False
    assert len(res["errors"]) == 1
    assert "belongs to Company 10, not 999" in res["errors"][0]


def test_hierarchy_validation_invalid_designation_company_and_main_dept_mismatch():
    db = create_mock_db()
    repo = OrganizationSourceRepository(db)

    # 1. Company mismatch for designation
    res_comp = repo.validate_hierarchy(
        company_id=999,
        desig_id=500,
    )
    assert res_comp["is_valid"] is False
    assert any("belongs to Company 10, not 999" in e for e in res_comp["errors"])

    # 2. Main Department mismatch for designation
    res_md = repo.validate_hierarchy(
        main_dept_id=888,
        desig_id=500,
    )
    assert res_md["is_valid"] is False
    assert any("belongs to Main Department 5, not 888" in e for e in res_md["errors"])

    # 3. Department mismatch for designation
    res_dept = repo.validate_hierarchy(
        dept_id=777,
        desig_id=500,
    )
    assert res_dept["is_valid"] is False
    assert any("belongs to Department 50, not 777" in e for e in res_dept["errors"])


def test_vacancy_mapping_populates_full_hierarchy_ids():
    from app.models.mssql.vacancy import RecruitVacancyRequest
    from app.services.vacancy_service import VacancyService

    db = MagicMock()
    bg1 = OrgBusinessGroupMst(BusinessGrpID=1, BusinessGrpName="Aether Group")
    comp1 = OrgCompanyMst(CompID=10, BusinessGrpID=1, CompName="Aether Chem")
    loc1 = OrgLocationMst(LocID=100, CompID=10, LocName="Surat Plant")
    main_dept1 = OrgMainDepartmentMst(MainDeptID=5, DeptName="Manufacturing")
    dept1 = OrgDepartmentMst(DeptID=50, CompID=10, MainDeptID=5, DeptName="Production")
    desig1 = OrgDesignationMst(DesigID=500, CompID=10, DeptID=50, MainDeptID=5, DesigName="Plant Chemist")

    vacancy = RecruitVacancyRequest(
        VacancyRequestID=1065,
        JobProfileID=42,
        RequestForCompID=10,
        RequestForLocationID=100,
        RequestForMainDeptID=5,
        RequestForDeptID=50,
        RequestForDesigID=500,
        PreferedGender="Any",
    )
    vacancy.company = comp1
    vacancy.location = loc1
    vacancy.department = dept1
    vacancy.designation = desig1
    vacancy.job_profile = None

    def scalar_mock(stmt):
        stmt_str = str(stmt).lower()
        if "orgbusinessgroupmst" in stmt_str:
            return bg1
        if "orgmaindepartmentmst" in stmt_str:
            return main_dept1
        return None

    db.scalar.side_effect = scalar_mock

    service = VacancyService(db)
    job_opening = service.map_to_job_requirement(vacancy)

    assert job_opening.vacancy_id == 1065
    assert job_opening.job_profile_id == 42
    assert job_opening.business_group_id == 1
    assert job_opening.business_group_name == "Aether Group"
    assert job_opening.company_id == 10
    assert job_opening.company_name_db == "Aether Chem"
    assert job_opening.location_id == 100
    assert job_opening.location_name_db == "Surat Plant"
    assert job_opening.main_department_id == 5
    assert job_opening.main_department_name == "Manufacturing"
    assert job_opening.department_id == 50
    assert job_opening.department_name == "Production"
    assert job_opening.designation_id == 500
    assert job_opening.designation_name == "Plant Chemist"

