from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.prompts.match_analysis import build_cv_job_prompt, build_job_requirements
from app.prompts.optimized_match import build_optimized_match_prompt
from app.schemas.analysis import (
    OptimizedCandidateProfile,
    OptimizedLLMMatchResponse,
    OptimizedVacancyMatch,
    RequirementAssessment,
)
from app.services.llm_grounding_service import LLMGroundingService


def _job() -> dict:
    return {
        "vacancy_id": "vac-1",
        "title": "Backend Engineer",
        "required_skills": ["Python"],
        "required_skills_are_mandatory": True,
        "preferred_keywords": ["mentoring"],
        "min_experience_years": 4,
        "max_experience_years": 8,
        "education": "Bachelor degree required",
        "certifications": ["AWS certification preferred"],
        "technologies": ["Docker"],
        "responsibilities": ["Must build production APIs"],
        "description": "Own reliable backend services",
    }


def _narratives() -> dict[str, str]:
    return {
        "top_strength": "The CV explicitly documents Python API delivery, directly matching the vacancy requirement. This is the clearest technical overlap.",
        "main_concern": "The CV does not document every responsibility listed by the vacancy. Recruiters should verify the remaining ownership requirements.",
        "ai_match_explanation": "The assessment is supported by direct Python delivery evidence. Missing evidence for other requirements limits overall certainty.",
    }


def _base_assessment(overrides: dict | None = None) -> dict:
    base = {
        "requirement_id": "skill_1",
        "requirement": "Python",
        "category": "SKILL",
        "mandatory": True,
        "jd_evidence": "Python",
        "cv_evidence": "Python APIs",
        "match_type": "DIRECT",
        "conclusion": "Python is directly met by the candidate.",
        "rationale": "The CV directly supports the requirement.",
        "confidence": 0.95,
        "impact": "LOW",
    }
    if overrides:
        base.update(overrides)
    return base


def test_requirement_builder_covers_all_supported_jd_categories_and_explicit_mandatory_flags():
    requirements = build_job_requirements(_job())

    assert [item["category"] for item in requirements] == [
        "SKILL",
        "PREFERRED_KEYWORD",
        "EXPERIENCE",
        "EXPERIENCE",
        "EDUCATION",
        "CERTIFICATION",
        "TECHNOLOGY",
        "RESPONSIBILITY",
        "DESCRIPTION",
    ]
    by_id = {item["requirement_id"]: item for item in requirements}
    assert by_id["skill_1"]["mandatory"] is True
    assert by_id["preferred_keyword_1"]["mandatory"] is False
    assert by_id["education_1"]["mandatory"] is True
    assert by_id["certification_1"]["mandatory"] is False
    assert by_id["responsibility_1"]["mandatory"] is True


def test_both_prompt_builders_receive_normalized_requirement_records():
    with patch("app.services.prompt_service.PromptService.get_prompt", return_value="{input_json}") as prompt_get:
        build_cv_job_prompt("Python API developer", _job())
    legacy_input = prompt_get.call_args.kwargs["placeholders"]["input_json"]
    assert '"requirement_id": "skill_1"' in legacy_input
    assert '"mandatory": true' in legacy_input

    with patch("app.services.prompt_service.PromptService.get_prompt", return_value="{input_json}") as prompt_get:
        build_optimized_match_prompt("Python API developer", [_job()])
    optimized_input = prompt_get.call_args.args[1]["input_json"]
    assert '"requirements":[{"requirement_id":"skill_1"' in optimized_input
    assert '"category":"RESPONSIBILITY","mandatory":true' in optimized_input


def test_requirement_assessment_schema_enforces_enums_confidence_evidence_and_critical_mandatory_gap():
    base = _base_assessment()
    assert RequirementAssessment.model_validate(base).confidence == 0.95
    for match_type in ("INFERRED", "PARTIAL"):
        assert RequirementAssessment.model_validate({**base, "match_type": match_type}).match_type == match_type
    missing = RequirementAssessment.model_validate(
        {**base, "match_type": "MISSING", "cv_evidence": "", "impact": "CRITICAL",
         "conclusion": "Python is not evidenced in the CV."}
    )
    assert missing.cv_evidence == ""
    not_assessable = RequirementAssessment.model_validate(
        {**base, "mandatory": False, "match_type": "NOT_ASSESSABLE", "cv_evidence": "", "confidence": 0.0, "impact": "HIGH",
         "conclusion": "Python could not be assessed from the available CV text."}
    )
    assert not_assessable.match_type == "NOT_ASSESSABLE"

    for update in (
        {"match_type": "RELATED"},
        {"confidence": 1.1},
        {"cv_evidence": ""},
        {"match_type": "MISSING", "cv_evidence": "", "impact": "HIGH",
         "conclusion": "Python is not evidenced in the CV."},
    ):
        with pytest.raises(ValidationError):
            RequirementAssessment.model_validate({**base, **update})


def test_requirement_assessment_schema_requires_conclusion_field():
    """Omitting conclusion must raise a ValidationError."""
    base = _base_assessment()
    del base["conclusion"]
    with pytest.raises(ValidationError):
        RequirementAssessment.model_validate(base)


def test_requirement_assessment_schema_rejects_empty_conclusion():
    """An empty conclusion string must raise a ValidationError."""
    base = _base_assessment({"conclusion": ""})
    with pytest.raises(ValidationError):
        RequirementAssessment.model_validate(base)


def test_grounding_canonicalizes_evidence_downgrades_unsupported_claims_and_fills_omissions(monkeypatch):
    monkeypatch.setattr(settings, "LLM_GROUNDING_ENABLED", True)
    vacancy = {
        "vacancy_id": "vac-1",
        "title": "Backend Engineer",
        "required_skills": ["Python", "Kubernetes"],
        "required_skills_are_mandatory": True,
        "preferred_keywords": ["mentoring"],
    }
    response = OptimizedLLMMatchResponse(
        candidate_profile=OptimizedCandidateProfile(core_skills=["Python"]),
        matched_vacancies=[
            OptimizedVacancyMatch(
                vacancy_id="vac-1",
                semantic_reason="The candidate has one direct skill match and two unverified requirements.",
                semantic_fit_score=50.0,
                requirement_assessments=[
                    RequirementAssessment(
                        requirement_id="skill_1",
                        requirement="Changed model wording",
                        category="OTHER",
                        mandatory=False,
                        jd_evidence="Python",
                        cv_evidence="Python APIs",
                        match_type="DIRECT",
                        conclusion="Python is directly met by the candidate.",
                        rationale="Python is explicitly documented.",
                        confidence=0.95,
                        impact="LOW",
                    ),
                    RequirementAssessment(
                        requirement_id="skill_2",
                        requirement="Kubernetes",
                        category="SKILL",
                        mandatory=True,
                        jd_evidence="Kubernetes",
                        cv_evidence="Kubernetes administration",
                        match_type="DIRECT",
                        conclusion="Kubernetes is met by the candidate.",
                        rationale="The model claimed direct Kubernetes evidence.",
                        confidence=0.9,
                        impact="LOW",
                    ),
                ],
                **_narratives(),
            )
        ],
        active_vacancy_summary="One vacancy evaluated.",
        ai_career_summary="Backend profile.",
    )

    validated, report = LLMGroundingService.validate_optimized_response(
        response,
        cv_text="Backend engineer who built Python APIs.",
        vacancies=[vacancy],
    )
    assessments = validated.matched_vacancies[0].requirement_assessments

    assert [item.requirement_id for item in assessments] == ["skill_1", "skill_2", "preferred_keyword_1"]
    assert assessments[0].requirement == "Python"
    assert assessments[0].mandatory is True
    assert assessments[0].match_type == "DIRECT"
    assert assessments[1].match_type == "NOT_ASSESSABLE"
    assert assessments[1].confidence == 0.0
    assert assessments[2].match_type == "NOT_ASSESSABLE"
    # Grounding fallback must populate a non-empty conclusion for NOT_ASSESSABLE items
    assert assessments[1].conclusion and len(assessments[1].conclusion) > 0
    assert assessments[2].conclusion and len(assessments[2].conclusion) > 0
    assert validated.matched_vacancies[0].classified_requirements[0].requirement_id == "skill_1"
    assert validated.matched_vacancies[0].evidence_snippets["skill_1"].cv_evidence == "Python APIs"
    assert any(claim.endswith("cv:skill_2") for claim in report.unsupported_claims)
    assert any(claim.endswith("omitted:preferred_keyword_1") for claim in report.unsupported_claims)


def test_migration_versions_both_prompts_and_restores_prior_versions_on_rollback():
    migrations = Path(__file__).parents[1] / "scripts" / "migrations" / "postgres"
    up = (migrations / "030_match_analysis_per_requirement_evidence.sql").read_text(encoding="utf-8")
    down = (migrations / "030_match_analysis_per_requirement_evidence_down.sql").read_text(encoding="utf-8")

    assert "version_tag = '1.1.0'" in up
    assert "'1.2.0'" in up
    assert "response-schema/v3" in up
    assert "conclusion" in up
    assert "conclusion must be one recruiter-facing verdict sentence" in up
    assert "'4.0'" in up
    assert "response-schema/v5" in up
    assert "version_tag = '1.2.0'" in down
    assert "version_tag = '1.1.0'" in down
    assert "'4.0'" in down
    assert "'3.9'" in down


def test_migration_029_versions_still_intact():
    """Sanity check: migration 029 is not modified by 030."""
    migrations = Path(__file__).parents[1] / "scripts" / "migrations" / "postgres"
    up = (migrations / "029_requirement_level_match_analysis.sql").read_text(encoding="utf-8")
    down = (migrations / "029_requirement_level_match_analysis_down.sql").read_text(encoding="utf-8")

    assert "version_tag = '3.8'" in up
    assert "'3.9'" in up
    assert "response-schema/v4" in up
    assert "REQUIREMENT ASSESSMENTS:" in up
    assert "'1.1.0'" in up
    assert "version_tag = '3.8'" in down
    assert "version_tag = '3.9'" in down

