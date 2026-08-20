"""
Unit tests for Phase 3 Fallback Governance, Availability Bounds & Data Fabrication Prevention.

Verifies:
1. AnalysisVersions exposes policy_source and degraded_mode diagnostic metadata.
2. Fallback logic never manufactures candidate facts or vacancy records when attributes are missing.
3. Degraded mode execution explicitly reports degraded_mode=True and non-equivalent policy provenance.
"""

from __future__ import annotations

from app.schemas.analysis_versions import AnalysisVersions
from app.schemas.contracts import EvidenceResult, EvidenceStatus
from app.services.vacancy_service import VacancyService


def test_analysis_versions_degraded_provenance_fields():
    """Verify AnalysisVersions contains policy_source and degraded_mode fields."""
    versions = AnalysisVersions(
        policy_source="bundled_static",
        degraded_mode=True,
    )
    assert versions.policy_source == "bundled_static"
    assert versions.degraded_mode is True


def test_no_manufactured_vacancy_organization_data():
    """Verify missing vacancy organization data returns None rather than manufactured placeholder strings."""
    from unittest.mock import MagicMock
    service = VacancyService(db=MagicMock())
    
    # Simulate DB model with None organization relations
    class DummyVacancy:
        VacancyRequestID = 101
        job_profile = None
        designation = None
        department = None
        company = None
        location = None
        RequestedAdditionalKnowledge = None
        RequestForCompID = None
        RequestForLocationID = None
        RequestForDeptID = None
        RequestForMainDeptID = None
        RequestForDesigID = None
        JobProfileID = None
        RequestedExperienceRangeFrom = None
        RequestedExperienceRangeTo = None
        RequestedCTCRangeFrom = None
        RequestedCTCRangeTo = None
        PreferedGender = None

    opening = service.map_to_job_requirement(DummyVacancy())
    assert opening.department_name is None
    assert opening.company_name is None
    assert opening.location_name is None


def test_degraded_mode_evidence_result():
    """Verify fallback EvidenceResult explicitly tags degraded_mode and status."""
    res = EvidenceResult.system_unavailable("Vector DB unavailable")
    assert res.status == EvidenceStatus.SYSTEM_UNAVAILABLE
    assert res.degraded_mode is True
    assert res.source == "system"
