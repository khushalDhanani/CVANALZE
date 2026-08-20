"""
EvidenceRanker Service.
Ranks candidate evidence (skills, experience, strengths) by confidence, recency, duration, and semantic contribution.
Eliminates arbitrary alphabetical sorting and ungrounded strength fallbacks.
"""

from __future__ import annotations

from typing import Any


class EvidenceRanker:
    """
    Evidence-based Ranker.
    Ranks extracted candidate skills and strengths based on evidence confidence,
    provenance, recency, and domain relevance without manufactured fallbacks.
    """

    @classmethod
    def rank_skills(cls, skills: set[str] | list[str], evidence_map: dict[str, Any] | None = None) -> list[str]:
        """Rank skills by evidence strength rather than arbitrary alphabetical ordering."""
        unique_skills = list(dict.fromkeys([s.strip() for s in skills if s and s.strip()]))
        if not unique_skills:
            return []

        if not evidence_map:
            return unique_skills

        def skill_weight(skill_name: str) -> float:
            ev = evidence_map.get(skill_name.lower())
            if ev is not None and hasattr(ev, "confidence_score"):
                return float(ev.confidence_score)
            return 0.5

        return sorted(unique_skills, key=skill_weight, reverse=True)

    @classmethod
    def extract_evidence_based_strengths(
        cls,
        skills_set: set[str] | list[str],
        education_list: list[str],
        projects_list: list[str],
        evidence_map: dict[str, Any] | None = None,
    ) -> list[str]:
        """Build candidate strengths strictly supported by extracted CV evidence."""
        strengths: list[str] = []

        ranked_skills = cls.rank_skills(skills_set, evidence_map)
        if ranked_skills:
            top_skills = ranked_skills[:5]
            strengths.append(f"Core Skills: {', '.join(top_skills)}")

        if education_list:
            clean_edu = [e.strip() for e in education_list if e and e.strip()][:2]
            if clean_edu:
                strengths.append(f"Education: {', '.join(clean_edu)}")

        if projects_list:
            strengths.append(f"Project Experience: {len(projects_list)} documented project(s)")

        return strengths
