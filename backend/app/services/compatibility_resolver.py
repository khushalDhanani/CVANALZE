"""
CompatibilityResolver Service.
Single authority for job-family and domain compatibility ranking and relation resolution.
"""

from __future__ import annotations

from typing import Any

from app.schemas.classification_types import TaxonomyRelationType


class CompatibilityResolver:
    """
    Unified Compatibility Resolver.
    Provides single-source authority for family and domain compatibility lookup,
    returning structured relation types (EXACT, ALLOWED, RELATED, DISALLOWED, UNKNOWN)
    and single-authority ranking weights.
    """

    DEFAULT_RANKING_WEIGHTS: dict[TaxonomyRelationType, float] = {
        TaxonomyRelationType.EXACT: 1.0,
        TaxonomyRelationType.ALLOWED: 0.85,
        TaxonomyRelationType.RELATED: 0.60,
        TaxonomyRelationType.DISALLOWED: 0.0,
        TaxonomyRelationType.UNKNOWN: 0.0,
    }

    @classmethod
    def resolve_relation(
        cls,
        family_a: str | None,
        family_b: str | None,
        compatibility_records: list[dict[str, Any]] | None = None,
    ) -> TaxonomyRelationType:
        """Resolve relation type between two job family or department codes/names."""
        clean_a = str(family_a or "").strip().lower()
        clean_b = str(family_b or "").strip().lower()

        if not clean_a or not clean_b:
            return TaxonomyRelationType.UNKNOWN

        if clean_a == clean_b:
            return TaxonomyRelationType.EXACT

        if compatibility_records:
            for rec in compatibility_records:
                rec_a = str(rec.get("family_a", "")).strip().lower()
                rec_b = str(rec.get("family_b", "")).strip().lower()
                if (clean_a == rec_a and clean_b == rec_b) or (clean_a == rec_b and clean_b == rec_a):
                    is_allowed = rec.get("is_allowed", True)
                    status = str(rec.get("status", "ALLOWED")).upper()
                    if not is_allowed or status == "DISALLOWED":
                        return TaxonomyRelationType.DISALLOWED
                    if status == "RELATED":
                        return TaxonomyRelationType.RELATED
                    return TaxonomyRelationType.ALLOWED

        return TaxonomyRelationType.UNKNOWN

    @classmethod
    def get_ranking_weight(cls, relation_type: TaxonomyRelationType) -> float:
        """Return the authoritative ranking weight for a given relation type."""
        return cls.DEFAULT_RANKING_WEIGHTS.get(relation_type, 0.0)
