from __future__ import annotations

from app.services.evidence_ranker import EvidenceRanker
from app.services.recommendation_service import RecommendationService


def test_empty_validated_projects_do_not_create_project_strength() -> None:
    strengths = EvidenceRanker.extract_evidence_based_strengths(
        skills_set=[],
        education_list=[],
        projects_list=[],
    )

    assert not any("Project Experience" in value for value in strengths)


def test_equivalent_missing_skill_gaps_are_deduplicated() -> None:
    gaps = [
        {"requirement": "Missing Skill: Process Analysis", "type": "Skill"},
        {"requirement": "Skill Gap (Process Analysis)", "type": "Criterion"},
    ]

    assert RecommendationService._deduplicate_missing_qualifications(gaps) == [gaps[0]]


def test_interview_focus_preserves_acronyms_and_expresses_department_ambiguity() -> None:
    focus = RecommendationService._build_interview_focus(
        missing_qualifications=[{"requirement": "Missing Skill: Process Analysis"}],
        candidate_skills=["SAP", "DCS (Yokogawa/Honeywell)"],
        primary_department="Process & Project Team",
        authoritative_department=False,
    )

    assert focus == [
        "Probe deeply on gaps: Missing Skill: Process Analysis",
        "Validate claimed expertise in SAP and DCS (Yokogawa/Honeywell).",
        "Clarify departmental fit before assigning Process & Project Team.",
    ]


def test_interview_focus_handles_pid_and_education_requirement() -> None:
    focus = RecommendationService._build_interview_focus(
        missing_qualifications=[
            {"requirement": "Bachelor degree required", "type": "Education"},
        ],
        candidate_skills=["p&id"],
        primary_department="Engineering",
        authoritative_department=True,
        education_evidence=["B.E. Chemical"],
    )

    assert any("P&ID" in item for item in focus)
    assert any("B.E. Chemical" in item for item in focus)


def test_manual_review_or_low_confidence_department_is_not_authoritative() -> None:
    assert not RecommendationService._is_authoritative_department(
        department_id=1,
        department_name="Engineering",
        confidence=0.9,
        manual_review_required=True,
    )
    assert not RecommendationService._is_authoritative_department(
        department_id=1,
        department_name="Engineering",
        confidence=0.2,
        manual_review_required=False,
    )


def test_legacy_cross_mapped_projects_are_not_counted_as_strengths() -> None:
    resume_json = {
        "projects": [
            {"name": "Professional Profile Summary", "description": "Summary text"},
            {"name": "Shift Engineer", "description": "Example Ltd | March 2021 – March 2024"},
            {"name": "Declaration", "description": "Declaration text"},
        ]
    }

    assert RecommendationService._validated_project_count(resume_json, extraction_integrity=None) == 0
    assert RecommendationService._validated_project_count(
        {"projects": [{"name": "Forecasting Project", "technologies": ["Python"]}]},
        extraction_integrity=None,
    ) == 1
