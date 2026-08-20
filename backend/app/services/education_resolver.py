from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel


class DegreeLevel(int, Enum):
    DOCTORATE = 5
    MASTERS = 4
    BACHELORS = 3
    DIPLOMA = 2
    HIGH_SCHOOL = 1
    UNKNOWN = 0


class DisciplineCategory(str, Enum):
    COMPUTER_SCIENCE = "COMPUTER_SCIENCE"
    INFORMATION_TECHNOLOGY = "INFORMATION_TECHNOLOGY"
    ENGINEERING = "ENGINEERING"
    FINANCE = "FINANCE"
    BUSINESS = "BUSINESS"
    HUMANITIES = "HUMANITIES"
    SCIENCE = "SCIENCE"
    OTHER = "OTHER"


class EducationMatchStatus(str, Enum):
    EXACT = "EXACT"
    EQUIVALENT = "EQUIVALENT"
    DEGREE_LEVEL_MISMATCH = "DEGREE_LEVEL_MISMATCH"
    DISCIPLINE_MISMATCH = "DISCIPLINE_MISMATCH"
    NOT_MATCHED = "NOT_MATCHED"


class EducationMatchOutcome(BaseModel):
    status: EducationMatchStatus
    confidence: float
    failure_code: str | None = None
    matched_degree: str | None = None
    required_degree_level: str
    candidate_degree_level: str
    reason: str


class EducationRequirementResolver:
    """
    Evaluates education requirements by explicitly separating degree level, discipline/specialization,
    and institution. B.Tech CS vs BA History fails with DISCIPLINE_MISMATCH; configured equivalent
    degrees (B.E. IT vs B.Tech CS) pass with EQUIVALENT.
    """

    _DEGREE_LEVEL_MAP: dict[str, DegreeLevel] = {
        "ph.d": DegreeLevel.DOCTORATE,
        "phd": DegreeLevel.DOCTORATE,
        "doctorate": DegreeLevel.DOCTORATE,
        "m.tech": DegreeLevel.MASTERS,
        "mtech": DegreeLevel.MASTERS,
        "m.s": DegreeLevel.MASTERS,
        "ms": DegreeLevel.MASTERS,
        "m.sc": DegreeLevel.MASTERS,
        "msc": DegreeLevel.MASTERS,
        "master": DegreeLevel.MASTERS,
        "masters": DegreeLevel.MASTERS,
        "mba": DegreeLevel.MASTERS,
        "m.e": DegreeLevel.MASTERS,
        "me": DegreeLevel.MASTERS,
        "b.tech": DegreeLevel.BACHELORS,
        "btech": DegreeLevel.BACHELORS,
        "b.e": DegreeLevel.BACHELORS,
        "be": DegreeLevel.BACHELORS,
        "b.s": DegreeLevel.BACHELORS,
        "bs": DegreeLevel.BACHELORS,
        "b.sc": DegreeLevel.BACHELORS,
        "bsc": DegreeLevel.BACHELORS,
        "bachelor": DegreeLevel.BACHELORS,
        "bachelors": DegreeLevel.BACHELORS,
        "b.a": DegreeLevel.BACHELORS,
        "ba": DegreeLevel.BACHELORS,
        "b.com": DegreeLevel.BACHELORS,
        "bcom": DegreeLevel.BACHELORS,
        "diploma": DegreeLevel.DIPLOMA,
        "high school": DegreeLevel.HIGH_SCHOOL,
        "secondary": DegreeLevel.HIGH_SCHOOL,
    }

    _DISCIPLINE_EQUIVALENTS: dict[DisciplineCategory, set[DisciplineCategory]] = {
        DisciplineCategory.COMPUTER_SCIENCE: {DisciplineCategory.COMPUTER_SCIENCE, DisciplineCategory.INFORMATION_TECHNOLOGY, DisciplineCategory.ENGINEERING},
        DisciplineCategory.INFORMATION_TECHNOLOGY: {DisciplineCategory.INFORMATION_TECHNOLOGY, DisciplineCategory.COMPUTER_SCIENCE, DisciplineCategory.ENGINEERING},
        DisciplineCategory.ENGINEERING: {DisciplineCategory.ENGINEERING, DisciplineCategory.COMPUTER_SCIENCE, DisciplineCategory.INFORMATION_TECHNOLOGY},
        DisciplineCategory.FINANCE: {DisciplineCategory.FINANCE, DisciplineCategory.BUSINESS},
        DisciplineCategory.BUSINESS: {DisciplineCategory.BUSINESS, DisciplineCategory.FINANCE},
    }

    @classmethod
    def resolve_degree_level(cls, text: str) -> DegreeLevel:
        if not text:
            return DegreeLevel.UNKNOWN
        clean = text.lower()
        for token, level in cls._DEGREE_LEVEL_MAP.items():
            if re.search(rf"\b{re.escape(token)}\b", clean):
                return level
        return DegreeLevel.UNKNOWN

    @classmethod
    def resolve_discipline(cls, text: str) -> DisciplineCategory:
        if not text:
            return DisciplineCategory.OTHER
        clean = text.lower()
        if any(kw in clean for kw in ("computer science", "cs", "computer engineering", "software engineering", "computing")):
            return DisciplineCategory.COMPUTER_SCIENCE
        if any(kw in clean for kw in ("information technology", "it", "information systems", "software systems")):
            return DisciplineCategory.INFORMATION_TECHNOLOGY
        if any(kw in clean for kw in ("finance", "accounting", "economics", "financial", "valuation")):
            return DisciplineCategory.FINANCE
        if any(kw in clean for kw in ("business", "management", "administration", "mba")):
            return DisciplineCategory.BUSINESS
        if any(kw in clean for kw in ("history", "arts", "literature", "english", "philosophy", "sociology")):
            return DisciplineCategory.HUMANITIES
        if any(kw in clean for kw in ("physics", "chemistry", "biology", "mathematics", "stats", "statistics")):
            return DisciplineCategory.SCIENCE
        if "engineering" in clean or "engg" in clean:
            return DisciplineCategory.ENGINEERING
        return DisciplineCategory.OTHER

    @classmethod
    def evaluate_education_requirement(
        cls,
        candidate_edu_entries: list[dict[str, Any] | str],
        required_edu: str,
    ) -> EducationMatchOutcome:

        req_level = cls.resolve_degree_level(required_edu)
        req_discipline = cls.resolve_discipline(required_edu)

        if not candidate_edu_entries:
            return EducationMatchOutcome(
                status=EducationMatchStatus.NOT_MATCHED,
                confidence=0.0,
                failure_code="MISSING_EDUCATION",
                required_degree_level=req_level.name,
                candidate_degree_level=DegreeLevel.UNKNOWN.name,
                reason=f"Candidate resume contains no education entries to satisfy required education '{required_edu}'",
            )

        best_cand_level = DegreeLevel.UNKNOWN
        best_cand_degree_str = ""
        discipline_matched = False
        discipline_equivalent = False

        for entry in candidate_edu_entries:
            if isinstance(entry, dict):
                degree_str = f"{entry.get('degree', '')} {entry.get('field_of_study', '')} {entry.get('institution', '')}"
            else:
                degree_str = str(entry)

            cand_level = cls.resolve_degree_level(degree_str)
            cand_discipline = cls.resolve_discipline(degree_str)

            if cand_level > best_cand_level:
                best_cand_level = cand_level
                best_cand_degree_str = degree_str

            if req_discipline != DisciplineCategory.OTHER:
                if cand_discipline == req_discipline:
                    discipline_matched = True
                elif cand_discipline in cls._DISCIPLINE_EQUIVALENTS.get(req_discipline, set()):
                    discipline_equivalent = True

        # Check degree level sufficiency
        if req_level != DegreeLevel.UNKNOWN and best_cand_level < req_level:
            return EducationMatchOutcome(
                status=EducationMatchStatus.DEGREE_LEVEL_MISMATCH,
                confidence=0.0,
                failure_code="DEGREE_LEVEL_MISMATCH",
                matched_degree=best_cand_degree_str or None,
                required_degree_level=req_level.name,
                candidate_degree_level=best_cand_level.name,
                reason=f"Required degree level '{req_level.name}' is higher than candidate highest level '{best_cand_level.name}'",
            )

        # Check discipline match
        if req_discipline != DisciplineCategory.OTHER and not discipline_matched and not discipline_equivalent:
            return EducationMatchOutcome(
                status=EducationMatchStatus.DISCIPLINE_MISMATCH,
                confidence=0.0,
                failure_code="DISCIPLINE_MISMATCH",
                matched_degree=best_cand_degree_str or None,
                required_degree_level=req_level.name,
                candidate_degree_level=best_cand_level.name,
                reason=f"Candidate discipline does not match required discipline '{req_discipline.value}'",
            )

        match_status = EducationMatchStatus.EXACT if discipline_matched or req_discipline == DisciplineCategory.OTHER else EducationMatchStatus.EQUIVALENT
        confidence = 1.0 if match_status == EducationMatchStatus.EXACT else 0.85

        return EducationMatchOutcome(
            status=match_status,
            confidence=confidence,
            matched_degree=best_cand_degree_str or None,
            required_degree_level=req_level.name,
            candidate_degree_level=best_cand_level.name,
            reason=f"Candidate education satisfies required education '{required_edu}'",
        )
