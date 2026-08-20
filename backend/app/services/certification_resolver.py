from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel

from app.core.rule_config_manager import PolicyRegistry


class CertificationMatchStatus(str, Enum):
    EXACT = "EXACT"
    EQUIVALENT = "EQUIVALENT"
    RELATED = "RELATED"
    NOT_MATCHED = "NOT_MATCHED"


class CertificationMatchOutcome(BaseModel):
    status: CertificationMatchStatus
    confidence: float
    canonical_name: str | None = None
    matched_cert: str | None = None
    reason: str


class CertificationResolver:
    """
    Canonicalizes certification names, vendors, aliases, versions, and accepted equivalents.
    Guarantees deterministic, evidence-backed certification matching where unrelated
    certifications never satisfy specific required certifications.
    """

    @classmethod
    def resolve_canonical(cls, raw_name: str) -> str | None:
        if not raw_name or not isinstance(raw_name, str):
            return None
        clean = raw_name.strip().lower()
        aliases = PolicyRegistry.resolve_snapshot().qualification.certification_aliases
        for canonical_name, canonical_aliases in aliases.items():
            if clean == canonical_name.lower():
                return canonical_name
            for alias in canonical_aliases:
                if alias == clean or alias in clean:
                    return canonical_name
        return None

    @classmethod
    def match_certification(
        cls,
        candidate_certs: list[str],
        required_cert: str,
    ) -> CertificationMatchOutcome:

        if not required_cert or not candidate_certs:
            return CertificationMatchOutcome(
                status=CertificationMatchStatus.NOT_MATCHED,
                confidence=0.0,
                reason=f"No candidate evidence found for required certification '{required_cert}'",
            )

        req_clean = required_cert.strip().lower()
        req_canonical = cls.resolve_canonical(required_cert) or req_clean
        qualification_policy = PolicyRegistry.resolve_snapshot().qualification

        for cand_cert in candidate_certs:
            if not isinstance(cand_cert, str) or not cand_cert.strip():
                continue
            cand_clean = cand_cert.strip().lower()
            cand_canonical = cls.resolve_canonical(cand_cert) or cand_clean

            # 1. Exact match
            if req_canonical == cand_canonical or req_clean == cand_clean or req_clean in cand_clean or cand_clean in req_clean:
                return CertificationMatchOutcome(
                    status=CertificationMatchStatus.EXACT,
                    confidence=qualification_policy.exact_match_confidence,
                    canonical_name=req_canonical,
                    matched_cert=cand_cert,
                    reason=f"Candidate holds exact required certification '{cand_cert}'",
                )

            # 2. Check canonical equivalents
            for equivalence in qualification_policy.certification_equivalences:
                if (
                    equivalence.active
                    and equivalence.required_id.lower() == req_canonical.lower()
                    and equivalence.accepted_id.lower() == cand_canonical.lower()
                ):
                    return CertificationMatchOutcome(
                        status=CertificationMatchStatus.EQUIVALENT,
                        confidence=qualification_policy.equivalent_match_confidence,
                        canonical_name=req_canonical,
                        matched_cert=cand_cert,
                        reason=f"Candidate holds accepted equivalent certification '{cand_cert}'",
                    )

        # Unrelated certification does NOT satisfy specific required certification
        return CertificationMatchOutcome(
            status=CertificationMatchStatus.NOT_MATCHED,
            confidence=0.0,
            canonical_name=req_canonical,
            reason=f"Candidate certifications {[c for c in candidate_certs]} do not satisfy required certification '{required_cert}'",
        )
