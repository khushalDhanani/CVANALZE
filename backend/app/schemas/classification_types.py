from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class MatchStatus(str, Enum):
    DB_MATCH = "DB_MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    NO_SUITABLE_MATCH = "NO_SUITABLE_MATCH"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    SOURCE_DATA_UNAVAILABLE = "SOURCE_DATA_UNAVAILABLE"


class ClassificationEvidence(BaseModel):
    """Evidence for a single match component.

    Attributes:
        source: Origin of the evidence, e.g., "mssql_vacancy", "cv_skill",
                "cv_title", "cv_education".
        matched_term: The exact term from the CV or source that matched.
        matched_against: The entity it was matched against (DB designation, skill, etc.).
        confidence: Confidence score for this evidence in the range 0.0-1.0.
    """
    source: str = Field(..., description="Source of the evidence")
    matched_term: Optional[str] = Field(None, description="What matched")
    matched_against: Optional[str] = Field(None, description="What it matched against")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence for the evidence")

class AISuggestion(BaseModel):
    """AI‑generated career suggestion used when no DB match is found."""
    suggested_role: str = Field(..., description="Suggested role name")
    suggested_domain: str = Field(..., description="Suggested domain name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence for the suggestion")
    evidence: List[ClassificationEvidence] = Field(default_factory=list, description="Evidence supporting the suggestion")
    missing_requirements: List[str] = Field(default_factory=list, description="What is needed to increase confidence")

class NormalizedClassification(BaseModel):
    """Unified classification result that carries both raw DB identifiers and normalized industry labels.

    The model also includes confidence, match status and supporting evidence.
    """
    # Raw DB identifiers (MUST be real MSSQL IDs; never PostgreSQL aliases)
    db_business_group_id: Optional[int] = None
    db_business_group_name: Optional[str] = None
    db_company_id: Optional[int] = None
    db_company_name: Optional[str] = None
    db_location_id: Optional[int] = None
    db_location_name: Optional[str] = None
    db_main_department_id: Optional[int] = None
    db_main_department_name: Optional[str] = None
    db_department_id: Optional[int] = None
    db_department_name: Optional[str] = None
    db_designation_id: Optional[int] = None
    db_designation_name: Optional[str] = None

    # Normalized industry labels (derived from alias/normalizer)
    industry_department: Optional[str] = None
    industry_designation: Optional[str] = None
    industry_domain: Optional[str] = None

    # Classification quality
    match_status: MatchStatus = Field(..., description="One of: DB_MATCH, NO_SUITABLE_MATCH, INSUFFICIENT_EVIDENCE")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence of the classification")
    evidence: List[ClassificationEvidence] = Field(default_factory=list, description="Supporting evidence items")
    match_source: Optional[str] = None

    # When no DB match, provide optional AI suggestion
    ai_career_suggestion: Optional[AISuggestion] = None
