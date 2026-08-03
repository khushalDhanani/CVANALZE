from pydantic import BaseModel, Field


class NormalizedStringField(BaseModel):
    raw_value: str | None = None
    normalized_value: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


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


class NormalizedContact(BaseModel):
    email: NormalizedStringField = Field(default_factory=NormalizedStringField)
    phone: NormalizedStringField = Field(default_factory=NormalizedStringField)


class NormalizedExperienceSummary(BaseModel):
    deterministic_years: float | None = Field(default=None, ge=0.0)
    stated_years: float | None = Field(default=None, ge=0.0)
    authoritative_source: str = "none"
    validation_status: str = "unavailable"
    evidence: list[str] = Field(default_factory=list)


class NormalizedResume(BaseModel):
    contact: NormalizedContact = Field(default_factory=NormalizedContact)
    skills: list[NormalizedSkill] = Field(default_factory=list)
    education: list[NormalizedEducation] = Field(default_factory=list)
    employment: list[NormalizedEmployment] = Field(default_factory=list)
    experience: NormalizedExperienceSummary = Field(default_factory=NormalizedExperienceSummary)
