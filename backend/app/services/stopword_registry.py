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

    @classmethod
    def is_garbage_skill(cls, term: str | None) -> bool:
        """Return True if a given skill term is a known garbage or placeholder token."""
        if not term or not term.strip():
            return True
        clean = term.strip().lower()
        if len(clean) <= 1:
            return True

        from app.core.rule_config_manager import PolicyRegistry
        from app.services.dynamic_scoring_prefilter_service import DynamicScoringAndPrefilterService

        policy_terms = {
            token.strip().lower()
            for token in PolicyRegistry.resolve_snapshot().extraction.garbage_skill_terms
            if token.strip()
        }
        database_terms = DynamicScoringAndPrefilterService.get_stop_words()
        return clean in policy_terms or clean in database_terms

    @classmethod
    def filter_valid_skills(cls, raw_skills: list[str]) -> list[str]:
        """Filter out garbage skill tokens while preserving valid skills."""
        valid: list[str] = []
        for s in raw_skills:
            clean = s.strip()
            if not cls.is_garbage_skill(clean):
                valid.append(clean)
        return valid
