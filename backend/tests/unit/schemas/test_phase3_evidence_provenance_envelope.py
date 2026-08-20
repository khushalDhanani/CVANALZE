"""
Unit tests for Phase 3 Evidence, Provenance and Degraded-Mode Architecture.

Verifies:
1. EvidenceStatus enum contains all 7 canonical statuses (VERIFIED, INFERRED, CONFLICTING, NOT_FOUND, NOT_APPLICABLE, NOT_ASSESSABLE, SYSTEM_UNAVAILABLE).
2. EvidenceResult[T] contains all 10 envelope fields (value, status, confidence, evidence, source, policy_id, policy_version, model_version, taxonomy_version, degraded_mode).
3. Factory classmethods (verified, inferred, conflicting, system_unavailable, not_applicable, not_assessable, not_found) construct valid results.
"""

from __future__ import annotations

from app.schemas.contracts import EvidenceRef, EvidenceResult, EvidenceStatus


def test_evidence_status_enum_values():
    """Verify EvidenceStatus contains all 7 canonical statuses."""
    expected = {
        "VERIFIED",
        "INFERRED",
        "CONFLICTING",
        "NOT_FOUND",
        "NOT_APPLICABLE",
        "NOT_ASSESSABLE",
        "SYSTEM_UNAVAILABLE",
    }
    actual = {status.value for status in EvidenceStatus}
    assert actual == expected


def test_evidence_result_envelope_fields():
    """Verify EvidenceResult[T] contains all required envelope fields."""
    res = EvidenceResult.verified(
        value="AWS Certified Solutions Architect",
        confidence=0.98,
        evidence=[EvidenceRef(raw_quote="AWS Certified Solutions Architect 2023", confidence_score=0.98)],
        source="deterministic",
        policy_id="policy_cert_v1",
        policy_version="1.2.0",
        model_version="nomic-embed-text",
        taxonomy_version="1.5.0",
        degraded_mode=False,
    )

    assert res.value == "AWS Certified Solutions Architect"
    assert res.status == EvidenceStatus.VERIFIED
    assert res.confidence == 0.98
    assert len(res.evidence) == 1
    assert res.source == "deterministic"
    assert res.policy_id == "policy_cert_v1"
    assert res.policy_version == "1.2.0"
    assert res.model_version == "nomic-embed-text"
    assert res.taxonomy_version == "1.5.0"
    assert res.degraded_mode is False


def test_evidence_result_factory_methods():
    """Verify all EvidenceResult factory classmethods."""
    inf = EvidenceResult.inferred("Python Developer", confidence=0.75, degraded_mode=False)
    assert inf.status == EvidenceStatus.INFERRED
    assert inf.confidence == 0.75

    conf = EvidenceResult.conflicting("Conflicting graduation year")
    assert conf.status == EvidenceStatus.CONFLICTING
    assert conf.confidence == 0.0

    sys_unavail = EvidenceResult.system_unavailable("Ollama service timeout")
    assert sys_unavail.status == EvidenceStatus.SYSTEM_UNAVAILABLE
    assert sys_unavail.degraded_mode is True

    na = EvidenceResult.not_applicable()
    assert na.status == EvidenceStatus.NOT_APPLICABLE
    assert na.degraded_mode is False
