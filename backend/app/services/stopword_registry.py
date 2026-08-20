"""
StopwordRegistry Service.
Centralized repository for data-quality stopwords, garbage terms, and normalization policies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class StopwordEntry:
    token: str
    category: Literal["GARBAGE_SKILL", "SECTION_HEADER", "SALUTATION", "STOP_WORD"]
    language: str = "en"
    active: bool = True
    version: str = "v2026.1"


class StopwordRegistry:
    """
    Centralized registry for data-quality vocabulary.
    Replaces embedded inline sets with versioned, categorized token policies.
    """

    GARBAGE_SKILLS: set[str] = {
        "-",
        ".",
        "yes",
        "no",
        "n/a",
        "na",
        "nil",
        "none",
        "test",
        "1",
        "0",
        "ok",
        "good",
        "e.g",
        "e.g.",
        "i.e",
        "i.e.",
        "job overview",
        "key responsibilities",
        "responsibilities",
        "requirements",
    }

    @classmethod
    def is_garbage_skill(cls, term: str | None) -> bool:
        """Return True if a given skill term is a known garbage or placeholder token."""
        if not term or not term.strip():
            return True
        clean = term.strip().lower()
        if len(clean) <= 1:
            return True
        return clean in cls.GARBAGE_SKILLS

    @classmethod
    def filter_valid_skills(cls, raw_skills: list[str]) -> list[str]:
        """Filter out garbage skill tokens while preserving valid skills."""
        valid: list[str] = []
        for s in raw_skills:
            clean = s.strip()
            if not cls.is_garbage_skill(clean):
                valid.append(clean)
        return valid
