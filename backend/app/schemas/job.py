from __future__ import annotations
from pydantic import BaseModel, Field


class JobOpening(BaseModel):
    id: str = Field(..., description="Unique job opening ID")
    title: str = Field(..., description="Job position title")
    department: str = Field(..., description="Department hosting this role")
    required_skills: list[str] = Field(default_factory=list, description="List of required skills")
    preferred_keywords: list[str] = Field(default_factory=list, description="List of preferred keywords")
    min_experience_years: float | None = Field(None, description="Minimum experience required")
    max_experience_years: float | None = Field(None, description="Maximum experience required")
    min_ctc: float | None = Field(None, description="Minimum CTC required")
    max_ctc: float | None = Field(None, description="Maximum CTC required")
    preferred_gender: str | None = Field(None, description="Preferred gender for the role")
    company_name: str | None = Field(None, description="Company name")
    location_name: str | None = Field(None, description="Location name")

    # Detailed Semantic Requirement Fields
    job_description: str | None = Field(None, description="Detailed job description")
    responsibilities: str | None = Field(None, description="Key responsibilities and duties")
    education: str | None = Field(None, description="Required education background")
    certifications: str | None = Field(None, description="Required or preferred certifications")

    # Live DB IDs & Full Organization Hierarchy
    vacancy_id: int | None = Field(None, description="Live MSSQL VacancyRequestID")
    job_profile_id: int | None = Field(None, description="Live MSSQL JobProfileID")
    business_group_id: int | None = Field(None, description="Live MSSQL BusinessGrpID")
    business_group_name: str | None = Field(None, description="Live MSSQL BusinessGrpName")
    company_id: int | None = Field(None, description="Live MSSQL CompID")
    company_name_db: str | None = Field(None, description="Live MSSQL CompName")
    location_id: int | None = Field(None, description="Live MSSQL LocID")
    location_name_db: str | None = Field(None, description="Live MSSQL LocName")
    main_department_id: int | None = Field(None, description="Live MSSQL MainDeptID")
    main_department_name: str | None = Field(None, description="Live MSSQL MainDeptName")
    department_id: int | None = Field(None, description="Live MSSQL DeptID")
    department_name: str | None = Field(None, description="Live MSSQL DeptName")
    designation_id: int | None = Field(None, description="Live MSSQL DesigID")
    designation_name: str | None = Field(None, description="Live MSSQL DesigName")

    # Taxonomy Metadata
    domain: str | None = Field(None, description="Taxonomy Domain")
    job_family: str | None = Field(None, description="Taxonomy Job Family")

    # Normalized industry labels (from DepartmentNormalizer)
    industry_title: str | None = Field(None, description="Normalized industry-standard job title")
    industry_department: str | None = Field(None, description="Normalized industry-standard department label")
