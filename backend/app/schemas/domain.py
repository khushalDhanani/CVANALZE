from pydantic import BaseModel, ConfigDict, Field


class DepartmentDomain(BaseModel):
    """
    Typed view of a DepartmentDomainMaster row plus its resolved department name.

    department_name is resolved from OrgDepartmentMst when available (DB mode);
    the bundled seed fallback supplies it directly.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int | None = Field(default=None, description="DepartmentDomainMaster.Id")
    department_id: int | None = Field(default=None, description="FK to OrgDepartmentMst.DeptID")
    department_name: str = Field(
        default="",
        description="Resolved department name (e.g. 'Information Technology')",
    )
    domain_name: str = Field(
        default="",
        description="Professional domain name (e.g. 'Information Technology & Software')",
    )
    keywords: list[str] = Field(default_factory=list, description="Keyword terms used for candidate matching")
    default_roles: list[str] = Field(default_factory=list, description="Suggested job roles for the domain")
    priority: int = Field(default=0, description="Lower priority value wins keyword-count ties")
    is_active: bool = Field(default=True, description="Whether the domain participates in matching")
