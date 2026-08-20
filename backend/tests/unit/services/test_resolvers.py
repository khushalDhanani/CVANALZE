from __future__ import annotations

import pytest

from app.services.certification_resolver import CertificationMatchStatus, CertificationResolver
from app.services.education_resolver import EducationMatchStatus, EducationRequirementResolver


def test_certification_resolver_exact_match() -> None:
    candidate_certs = ["AWS Certified Solutions Architect Professional", "Scrum Master"]
    required_cert = "AWS Certified Solutions Architect - Professional"

    outcome = CertificationResolver.match_certification(candidate_certs, required_cert)
    assert outcome.status == CertificationMatchStatus.EXACT
    assert outcome.confidence == 1.0
    assert outcome.matched_cert == "AWS Certified Solutions Architect Professional"


def test_certification_resolver_unrelated_cert_rejected() -> None:
    candidate_certs = ["Certified Scrum Master (CSM)", "ITIL Foundation"]
    required_cert = "AWS Certified Solutions Architect - Professional"

    outcome = CertificationResolver.match_certification(candidate_certs, required_cert)
    assert outcome.status == CertificationMatchStatus.NOT_MATCHED
    assert outcome.confidence == 0.0


def test_education_resolver_discipline_mismatch_fails() -> None:
    candidate_edu = [{"degree": "B.A.", "field_of_study": "History", "institution": "NYU"}]
    required_edu = "B.Tech in Computer Science"

    outcome = EducationRequirementResolver.evaluate_education_requirement(candidate_edu, required_edu)
    assert outcome.status == EducationMatchStatus.DISCIPLINE_MISMATCH
    assert outcome.failure_code == "DISCIPLINE_MISMATCH"
    assert outcome.confidence == 0.0


def test_education_resolver_degree_level_mismatch_fails() -> None:
    candidate_edu = [{"degree": "B.S.", "field_of_study": "Computer Science", "institution": "MIT"}]
    required_edu = "Ph.D. in Computer Science"

    outcome = EducationRequirementResolver.evaluate_education_requirement(candidate_edu, required_edu)
    assert outcome.status == EducationMatchStatus.DEGREE_LEVEL_MISMATCH
    assert outcome.failure_code == "DEGREE_LEVEL_MISMATCH"
    assert outcome.confidence == 0.0


def test_education_resolver_equivalent_discipline_passes() -> None:
    candidate_edu = [{"degree": "B.E.", "field_of_study": "Information Technology", "institution": "Mumbai University"}]
    required_edu = "B.Tech in Computer Science"

    outcome = EducationRequirementResolver.evaluate_education_requirement(candidate_edu, required_edu)
    assert outcome.status in (EducationMatchStatus.EXACT, EducationMatchStatus.EQUIVALENT)
    assert outcome.confidence >= 0.85
