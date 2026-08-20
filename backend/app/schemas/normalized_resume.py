from __future__ import annotations

from pydantic import BaseModel, Field


class NormalizedStringField(BaseModel):
    raw_value: str | None = None
    normalized_value: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.raw_value == other or self.normalized_value == other
        return super().__eq__(other)

    def __str__(self) -> str:
        return self.normalized_value or self.raw_value or ""


class NormalizedSkill(NormalizedStringField):
    aliases: list[str] = Field(default_factory=list)


class NormalizedDateInterval(BaseModel):
    raw_value: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    duration_months: int | None = Field(default=None, ge=0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class NormalizedEmployment(BaseModel):
    job_title: NormalizedStringField = Field(default_factory=NormalizedStringField)
    company: NormalizedStringField = Field(default_factory=NormalizedStringField)
    interval: NormalizedDateInterval = Field(default_factory=NormalizedDateInterval)
    responsibilities: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class NormalizedEducation(BaseModel):
    degree: NormalizedStringField = Field(default_factory=NormalizedStringField)
    domain: NormalizedStringField = Field(default_factory=NormalizedStringField)
    institution: NormalizedStringField = Field(default_factory=NormalizedStringField)
    interval: NormalizedDateInterval | None = None
    grade: NormalizedStringField | None = None
    evidence: list[str] = Field(default_factory=list)
    source_section: str | None = None
    source_heading: str | None = None


class NormalizedProject(BaseModel):
    name: NormalizedStringField = Field(default_factory=NormalizedStringField)
    description: NormalizedStringField = Field(default_factory=NormalizedStringField)
    technologies: list[str] = Field(default_factory=list)
    bullet_points: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    source_section: str | None = None
    source_heading: str | None = None


class NormalizedContact(BaseModel):
    email: NormalizedStringField = Field(default_factory=NormalizedStringField)
    phone: NormalizedStringField = Field(default_factory=NormalizedStringField)


class NormalizedExperienceSummary(BaseModel):
    experience_state: str = "UNKNOWN"
    gross_display: str = ""
    deterministic_years: float | None = Field(default=None, ge=0.0)
    stated_years: float | None = Field(default=None, ge=0.0)
    authoritative_years: float | None = Field(default=None, ge=0.0)
    total_experience_months: int | None = Field(default=None, ge=0)
    authoritative_source: str = "none"
    validation_status: str = "unavailable"
    evidence: list[str] = Field(default_factory=list)


class NormalizedResume(BaseModel):
    contact: NormalizedContact = Field(default_factory=NormalizedContact)
    skills: list[NormalizedSkill] = Field(default_factory=list)
    education: list[NormalizedEducation] = Field(default_factory=list)
    projects: list[NormalizedProject] = Field(default_factory=list)
    employment: list[NormalizedEmployment] = Field(default_factory=list)
    experience: NormalizedExperienceSummary = Field(default_factory=NormalizedExperienceSummary)
