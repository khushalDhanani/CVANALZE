from __future__ import annotations
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.mssql.organization import (
    OrgBusinessGroupMst,
    OrgCompanyMst,
    OrgLocationMst,
    OrgMainDepartmentMst,
    OrgDepartmentMst,
    OrgDesignationMst,
)


class OrganizationSourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_business_groups(self) -> list[OrgBusinessGroupMst]:
        """Fetch all active business groups."""
        return self.db.scalars(
            select(OrgBusinessGroupMst).where(
                (OrgBusinessGroupMst.BusinessGrpIsActive == True) | (OrgBusinessGroupMst.BusinessGrpIsActive.is_(None)),
                (OrgBusinessGroupMst.BusinessGrpIsDeleted == False) | (OrgBusinessGroupMst.BusinessGrpIsDeleted.is_(None)),
            )
        ).all()

    def get_companies(self, business_group_id: int | None = None) -> list[OrgCompanyMst]:
        """Fetch active companies, optionally filtered by BusinessGrpID."""
        stmt = select(OrgCompanyMst).where(
            (OrgCompanyMst.CompIsActive == True) | (OrgCompanyMst.CompIsActive.is_(None)),
            (OrgCompanyMst.CompIsDeleted == False) | (OrgCompanyMst.CompIsDeleted.is_(None)),
        )
        if business_group_id is not None:
            stmt = stmt.where(OrgCompanyMst.BusinessGrpID == business_group_id)
        return self.db.scalars(stmt).all()

    def get_locations(self, company_id: int | None = None) -> list[OrgLocationMst]:
        """Fetch active locations, optionally filtered by CompID."""
        stmt = select(OrgLocationMst).where(
            (OrgLocationMst.LocIsActive == True) | (OrgLocationMst.LocIsActive.is_(None)),
            (OrgLocationMst.LocIsDeleted == False) | (OrgLocationMst.LocIsDeleted.is_(None)),
        )
        if company_id is not None:
            stmt = stmt.where(OrgLocationMst.CompID == company_id)
        return self.db.scalars(stmt).all()

    def get_main_departments(self) -> list[OrgMainDepartmentMst]:
        """Fetch active main departments."""
        return self.db.scalars(
            select(OrgMainDepartmentMst).where(
                (OrgMainDepartmentMst.IsActive == True) | (OrgMainDepartmentMst.IsActive.is_(None))
            )
        ).all()

    def get_active_departments(self, company_id: int | None = None, main_dept_id: int | None = None) -> list[OrgDepartmentMst]:
        """Fetch active departments, optionally filtered by CompID or MainDeptID."""
        stmt = select(OrgDepartmentMst).where(
            (OrgDepartmentMst.DeptIsActive == True) | (OrgDepartmentMst.DeptIsActive.is_(None)),
            (OrgDepartmentMst.DeptIsDeleted == False) | (OrgDepartmentMst.DeptIsDeleted.is_(None)),
        )
        if company_id is not None:
            stmt = stmt.where(OrgDepartmentMst.CompID == company_id)
        if main_dept_id is not None:
            stmt = stmt.where(OrgDepartmentMst.MainDeptID == main_dept_id)
        return self.db.scalars(stmt).all()

    def get_all_designations(
        self, company_id: int | None = None, dept_id: int | None = None, main_dept_id: int | None = None
    ) -> list[OrgDesignationMst]:
        """Fetch active designations, optionally filtered by CompID, DeptID, or MainDeptID."""
        stmt = select(OrgDesignationMst).where(
            (OrgDesignationMst.DesigIsActive == True) | (OrgDesignationMst.DesigIsActive.is_(None)),
            (OrgDesignationMst.DesigIsDeleted == False) | (OrgDesignationMst.DesigIsDeleted.is_(None)),
        )
        if company_id is not None:
            stmt = stmt.where(OrgDesignationMst.CompID == company_id)
        if dept_id is not None:
            stmt = stmt.where(OrgDesignationMst.DeptID == dept_id)
        if main_dept_id is not None:
            stmt = stmt.where(OrgDesignationMst.MainDeptID == main_dept_id)
        return self.db.scalars(stmt).all()

    def validate_hierarchy(
        self,
        business_group_id: int | None = None,
        company_id: int | None = None,
        location_id: int | None = None,
        main_dept_id: int | None = None,
        dept_id: int | None = None,
        desig_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Validates parent-child relationships across the complete organization hierarchy.
        Returns {"is_valid": bool, "errors": list[str], "details": dict}.
        """
        errors: list[str] = []
        details: dict[str, Any] = {}

        # 1. Company -> BusinessGroup validation
        if company_id is not None:
            comp = self.db.scalar(select(OrgCompanyMst).where(OrgCompanyMst.CompID == company_id))
            if not comp:
                errors.append(f"Company ID {company_id} does not exist.")
            else:
                details["company_name"] = comp.CompName
                details["company_business_group_id"] = comp.BusinessGrpID
                if business_group_id is not None and comp.BusinessGrpID != business_group_id:
                    errors.append(
                        f"Company '{comp.CompName}' (ID {company_id}) belongs to Business Group {comp.BusinessGrpID}, not {business_group_id}."
                    )

        # 2. Location -> Company validation
        if location_id is not None:
            loc = self.db.scalar(select(OrgLocationMst).where(OrgLocationMst.LocID == location_id))
            if not loc:
                errors.append(f"Location ID {location_id} does not exist.")
            else:
                details["location_name"] = loc.LocName
                details["location_company_id"] = loc.CompID
                if company_id is not None and loc.CompID != company_id:
                    errors.append(
                        f"Location '{loc.LocName}' (ID {location_id}) belongs to Company {loc.CompID}, not {company_id}."
                    )

        # 3. Department -> Company & MainDept validation
        if dept_id is not None:
            dept = self.db.scalar(select(OrgDepartmentMst).where(OrgDepartmentMst.DeptID == dept_id))
            if not dept:
                errors.append(f"Department ID {dept_id} does not exist.")
            else:
                details["department_name"] = dept.DeptName
                details["department_company_id"] = dept.CompID
                details["department_main_dept_id"] = dept.MainDeptID
                if company_id is not None and dept.CompID != company_id:
                    errors.append(
                        f"Department '{dept.DeptName}' (ID {dept_id}) belongs to Company {dept.CompID}, not {company_id}."
                    )
                if main_dept_id is not None and dept.MainDeptID != main_dept_id:
                    errors.append(
                        f"Department '{dept.DeptName}' (ID {dept_id}) belongs to Main Department {dept.MainDeptID}, not {main_dept_id}."
                    )

        # 4. Designation -> Company, Dept & MainDept validation
        if desig_id is not None:
            desig = self.db.scalar(select(OrgDesignationMst).where(OrgDesignationMst.DesigID == desig_id))
            if not desig:
                errors.append(f"Designation ID {desig_id} does not exist.")
            else:
                details["designation_name"] = desig.DesigName
                details["designation_company_id"] = desig.CompID
                details["designation_dept_id"] = desig.DeptID
                details["designation_main_dept_id"] = desig.MainDeptID
                if company_id is not None and desig.CompID != company_id:
                    errors.append(
                        f"Designation '{desig.DesigName}' (ID {desig_id}) belongs to Company {desig.CompID}, not {company_id}."
                    )
                if dept_id is not None and desig.DeptID != dept_id:
                    errors.append(
                        f"Designation '{desig.DesigName}' (ID {desig_id}) belongs to Department {desig.DeptID}, not {dept_id}."
                    )
                if main_dept_id is not None and desig.MainDeptID != main_dept_id:
                    errors.append(
                        f"Designation '{desig.DesigName}' (ID {desig_id}) belongs to Main Department {desig.MainDeptID}, not {main_dept_id}."
                    )

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "details": details,
        }
