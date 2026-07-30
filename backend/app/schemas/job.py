from pydantic import BaseModel, Field


class JobOpening(BaseModel):
    id: str = Field(..., description="Unique job opening ID")
    title: str = Field(..., description="Job position title")
    department: str = Field(..., description="Department hosting this role")
    required_skills: list[str] = Field(
        default_factory=list, description="List of required skills"
    )
    preferred_keywords: list[str] = Field(
        default_factory=list, description="List of preferred keywords"
    )
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

    # Live DB IDs
    vacancy_id: int | None = Field(None, description="Live MSSQL VacancyRequestID")
    job_profile_id: int | None = Field(None, description="Live MSSQL JobProfileID")
    company_id: int | None = Field(None, description="Live MSSQL CompID")
    department_id: int | None = Field(None, description="Live MSSQL DeptID")
    department_name: str | None = Field(None, description="Live MSSQL DeptName")
    location_id: int | None = Field(None, description="Live MSSQL LocID")
