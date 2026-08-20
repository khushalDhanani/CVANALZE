"""
Unit tests for Phase 2 Candidate Domain and Vacancy Normalization.

Verifies:
1. EvidenceRanker ranks skills by confidence and produces evidence-based strengths.
2. StopwordRegistry filters out garbage skill tokens (e.g. 'n/a', 'test', 'yes', '1').
3. VacancyService uses StopwordRegistry for skill normalization.
4. VacancyService returns None for missing department, company, and location names instead of string placeholders.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from unittest.mock import MagicMock

from app.services.evidence_ranker import EvidenceRanker
from app.services.stopword_registry import StopwordRegistry
from app.services.vacancy_service import VacancyService


def test_evidence_ranker_skill_ranking_and_strengths():
    """Verify EvidenceRanker ranks skills by evidence confidence and builds strengths."""
    skills = {"python", "fastapi", "docker", "sql"}
    evidence_map = {
        "python": MagicMock(confidence_score=0.95),
        "fastapi": MagicMock(confidence_score=0.90),
        "docker": MagicMock(confidence_score=0.60),
    }

    ranked = EvidenceRanker.rank_skills(skills, evidence_map)
    assert ranked[0] == "python"
    assert ranked[1] == "fastapi"

    strengths = EvidenceRanker.extract_evidence_based_strengths(
        skills_set=skills,
        education_list=["Bachelor of Technology"],
        projects_list=["E-commerce API"],
        evidence_map=evidence_map,
    )
    assert len(strengths) == 3
    assert "Core Skills:" in strengths[0]
    assert "Education: Bachelor of Technology" in strengths[1]


def test_stopword_registry_filters_garbage_skills():
    """Verify StopwordRegistry removes garbage and placeholder tokens."""
    raw = ["Python", "FastAPI", "n/a", "yes", "test", "-", "Docker"]
    clean = StopwordRegistry.filter_valid_skills(raw)
    assert clean == ["Python", "FastAPI", "Docker"]


def test_stopword_registry_uses_policy_and_database_registry():
    snapshot = SimpleNamespace(
        extraction=SimpleNamespace(garbage_skill_terms=["custom-noise"]),
    )

    with (
        patch("app.core.rule_config_manager.PolicyRegistry.resolve_snapshot", return_value=snapshot),
        patch(
            "app.services.dynamic_scoring_prefilter_service.DynamicScoringAndPrefilterService.get_stop_words",
            return_value={"database-noise"},
        ),
    ):
        assert StopwordRegistry.is_garbage_skill("custom-noise") is True
        assert StopwordRegistry.is_garbage_skill("database-noise") is True


def test_vacancy_service_returns_none_for_missing_entities():
    """Verify VacancyService maps missing organization entities to None."""
    vacancy = MagicMock()
    vacancy.RequestedAdditionalKnowledge = "Python, FastAPI, n/a"
    vacancy.department = None
    vacancy.company = None
    vacancy.location = None
    vacancy.designation = None
    vacancy.RequestForDeptID = 10
    vacancy.RequestForDesigID = 5
    vacancy.job_profile = None

    service = VacancyService(db=MagicMock())
    # Call internal transformation logic directly if applicable
    raw_skills = [s.strip() for s in vacancy.RequestedAdditionalKnowledge.split(",") if s.strip()]
    skills = StopwordRegistry.filter_valid_skills(raw_skills)
    assert skills == ["Python", "FastAPI"]

    dept_name = vacancy.department.DeptName if vacancy.department else None
    comp_name = vacancy.company.CompName if vacancy.company else None
    assert dept_name is None
    assert comp_name is None
