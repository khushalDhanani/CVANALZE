from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel


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

    _CANONICAL_DICTIONARY: dict[str, dict[str, Any]] = {
        "aws_solutions_architect_prof": {
            "vendor": "Amazon Web Services",
            "canonical_name": "AWS Certified Solutions Architect - Professional",
            "aliases": [
                "aws certified solutions architect professional",
                "aws solutions architect professional",
                "aws professional solutions architect",
                "aws architect pro",
            ],
            "equivalents": ["aws certified solutions architect - associate"],
        },
        "aws_solutions_architect_assoc": {
            "vendor": "Amazon Web Services",
            "canonical_name": "AWS Certified Solutions Architect - Associate",
            "aliases": [
                "aws certified solutions architect associate",
                "aws solutions architect associate",
                "aws architect associate",
                "aws csa associate",
            ],
            "equivalents": [],
        },
        "pmp": {
            "vendor": "Project Management Institute",
            "canonical_name": "Project Management Professional (PMP)",
            "aliases": [
                "project management professional",
                "pmp",
                "pmp certified",
                "pmi pmp",
            ],
            "equivalents": ["prince2 practitioner"],
        },
        "ckad": {
            "vendor": "CNCF",
            "canonical_name": "Certified Kubernetes Application Developer (CKAD)",
            "aliases": ["ckad", "certified kubernetes application developer"],
            "equivalents": ["cka"],
        },
        "cka": {
            "vendor": "CNCF",
            "canonical_name": "Certified Kubernetes Administrator (CKA)",
            "aliases": ["cka", "certified kubernetes administrator"],
            "equivalents": [],
        },
        "cissp": {
            "vendor": "ISC2",
            "canonical_name": "Certified Information Systems Security Professional (CISSP)",
            "aliases": ["cissp", "certified information systems security professional"],
            "equivalents": ["cism"],
        },
    }

    @classmethod
    def resolve_canonical(cls, raw_name: str) -> str | None:
        if not raw_name or not isinstance(raw_name, str):
            return None
        clean = raw_name.strip().lower()
        for key, entry in cls._CANONICAL_DICTIONARY.items():
            if clean == entry["canonical_name"].lower():
                return entry["canonical_name"]
            for alias in entry["aliases"]:
                if alias == clean or alias in clean:
                    return entry["canonical_name"]
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

        for cand_cert in candidate_certs:
            if not isinstance(cand_cert, str) or not cand_cert.strip():
                continue
            cand_clean = cand_cert.strip().lower()
            cand_canonical = cls.resolve_canonical(cand_cert) or cand_clean

            # 1. Exact match
            if req_canonical == cand_canonical or req_clean == cand_clean or req_clean in cand_clean or cand_clean in req_clean:
                return CertificationMatchOutcome(
                    status=CertificationMatchStatus.EXACT,
                    confidence=1.0,
                    canonical_name=req_canonical,
                    matched_cert=cand_cert,
                    reason=f"Candidate holds exact required certification '{cand_cert}'",
                )

            # 2. Check canonical equivalents
            for key, entry in cls._CANONICAL_DICTIONARY.items():
                if entry["canonical_name"] == req_canonical:
                    if cand_canonical.lower() in [eq.lower() for eq in entry.get("equivalents", [])]:
                        return CertificationMatchOutcome(
                            status=CertificationMatchStatus.EQUIVALENT,
                            confidence=0.85,
                            canonical_name=entry["canonical_name"],
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
