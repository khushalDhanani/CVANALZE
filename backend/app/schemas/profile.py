from __future__ import annotations
from pydantic import BaseModel, Field


class CareerTransition(BaseModel):
    from_role: str = Field(..., description="The previous role or domain.")
    to_role: str = Field(..., description="The new role or domain.")
    reason_inferred: str = Field(..., description="Inferred reason for the transition based on the CV.")
    evidence: str = Field(..., description="Evidence from the CV supporting this transition.")


class TimelineEvent(BaseModel):
    title: str = Field(..., description="Job title, degree, or role.")
    organization: str = Field(..., description="Company, university, or organization name.")
    start_date: str = Field(..., description="Start date/year of the event.")
    end_date: str | None = Field(None, description="End date/year of the event. Null if present.")
    description: str = Field(..., description="Brief description of responsibilities or achievements.")


class DynamicCandidateProfile(BaseModel):
    education_domains: list[str] = Field(
        default_factory=list,
        description="Domains of education (e.g. Computer Science, Accounting).",
    )
    professional_domains: list[str] = Field(
        default_factory=list,
        description="Domains of professional experience (e.g. Software Engineering, Sales).",
    )
    current_domain: str = Field(..., description="The primary current professional domain.")
    current_role: str = Field(..., description="The most recent job title or role.")
    previous_roles: list[str] = Field(default_factory=list, description="List of previous job titles.")
    career_transitions: list[CareerTransition] = Field(
        default_factory=list,
        description="Any detected significant career or domain transitions.",
    )
    core_skills: list[str] = Field(
        default_factory=list,
        description="Core technical and soft skills demonstrated in the CV.",
    )
    relevant_experience_years: float = Field(
        ...,
        description="Total years of relevant professional experience, prioritizing recent roles.",
    )
    timeline: list[TimelineEvent] = Field(
        default_factory=list,
        description="Chronological timeline of education and experience.",
    )
    confidence: str = Field(
        ...,
        description="Confidence in the extracted profile: HIGH, MEDIUM, LOW, or UNCERTAIN.",
    )
    evidence_notes: str = Field(
        ...,
        description="Notes on why certain domains or roles were inferred and any conflicting evidence.",
    )
