from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MatchType(str, Enum):
    CASE_SENSITIVE_ACRONYM = "CASE_SENSITIVE_ACRONYM"
    CASE_INSENSITIVE_TOKEN = "CASE_INSENSITIVE_TOKEN"
    CASE_INSENSITIVE_PHRASE = "CASE_INSENSITIVE_PHRASE"


class KeywordConfig(BaseModel):
    term: str
    match_type: MatchType | None = None
    weight: float = 1.0


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
    keywords: list[KeywordConfig] = Field(default_factory=list, description="Keyword terms used for candidate matching")

    @field_validator("keywords", mode="before")
    @classmethod
    def parse_keywords(cls, v: Any) -> list[KeywordConfig]:
        if not isinstance(v, list):
            return []
        parsed = []
        for item in v:
            if isinstance(item, str):
                parsed.append(KeywordConfig(term=item))
            elif isinstance(item, dict):
                parsed.append(KeywordConfig(**item))
            elif isinstance(item, KeywordConfig):
                parsed.append(item)
        return parsed
    default_roles: list[str] = Field(default_factory=list, description="Suggested job roles for the domain")
    priority: int = Field(default=0, description="Lower priority value wins keyword-count ties")
    is_active: bool = Field(default=True, description="Whether the domain participates in matching")
