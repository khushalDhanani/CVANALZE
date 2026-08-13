from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.schemas.analysis import (
    ClassifiedRequirementItem,
    OptimizedCandidateProfile,
    OptimizedLLMMatchResponse,
    OptimizedVacancyMatch,
    RequirementEvidence,
)
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.job_context import JobEvaluationContext
from app.schemas.normalized_resume import NormalizedResume
from app.services.document_parser import (
    MarkdownGenerator,
    QualityMetricsCalculator,
    ResumeJsonExtractor,
    TextSanitizer,
)
from app.services.match_service import MatchService
from app.services.resume_normalizer import ResumeNormalizer
from app.services.vacancy_prefilter import VacancyPreFilter


def _structured_resume_text() -> str:
    return """
## Alex Smith
Email: Alex.Smith@Example.COM
Phone: +1 555 010 9999

## PROFILE SUMMARY
9 years of experience in software delivery.

## WORK EXPERIENCE
## Example Corp
Senior Developer (Jan 2020 - Dec 2021)
- Built Python and JavaScript APIs.

## EDUCATION
## University of Technology
BTech in Computer Science (2016 - 2020)

## SKILLS
Languages: Python, JS, SQL
"""


def test_document_parser_is_a_compatibility_facade():
    assert MarkdownGenerator.__module__ == "app.services.document_conversion"
    assert ResumeJsonExtractor.__module__ == "app.services.resume_field_extractor"
    assert QualityMetricsCalculator.__module__ == "app.services.resume_quality"
    assert TextSanitizer.__module__ == "app.services.resume_text_normalizer"


def test_normalized_resume_retains_raw_values_confidence_and_evidence():
    resume_json = ResumeJsonExtractor.extract(_structured_resume_text())
    normalized = NormalizedResume.model_validate(resume_json["normalized"])

    assert resume_json["contact_info"]["email"] == "Alex.Smith@Example.COM"
    assert normalized.contact.email.raw_value == "Alex.Smith@Example.COM"
    assert normalized.contact.email.normalized_value == "alex.smith@example.com"
    assert normalized.contact.email.confidence == 1.0
    assert normalized.contact.email.evidence == ["Alex.Smith@Example.COM"]

    assert normalized.contact.phone.raw_value == "+1 555 010 9999"
    assert normalized.contact.phone.normalized_value == "+15550109999"
    assert any(skill.normalized_value == "JavaScript" for skill in normalized.skills)
    assert normalized.education[0].degree.normalized_value == "B.Tech"
    assert normalized.education[0].domain.normalized_value == "Computer Science & IT"
    assert normalized.education[0].institution.normalized_value == "University of Technology"
    assert normalized.employment[0].interval.start_date == "2020-01-01"
    assert normalized.employment[0].interval.end_date == "2021-12-31"
    assert normalized.employment[0].interval.duration_months == 23
    assert normalized.experience.deterministic_years == 2.0
    assert normalized.experience.stated_years == 9.0
    assert normalized.experience.authoritative_source == "employment_dates"
    assert normalized.experience.validation_status == "stated_value_conflicts"


def test_candidate_context_keeps_dates_authoritative_and_uses_llm_only_as_fallback():
    resume_json = ResumeJsonExtractor.extract(_structured_resume_text())
    normalized = NormalizedResume.model_validate(resume_json["normalized"])
    llm_profile = OptimizedCandidateProfile(relevant_experience_years=12.0)

    dated_context = CandidateAnalysisContext.create(
        _structured_resume_text(),
        resume_json=resume_json,
        normalized_resume=normalized,
        optimized_profile=llm_profile,
    )
    assert dated_context.candidate_experience == 2.0

    undated_resume = {
        "contact_info": {},
        "work_experience": [],
        "education": [],
        "skills": {"all_skills": []},
    }
    undated_normalized = ResumeNormalizer.normalize(undated_resume, "Ten years stated without dated roles")
    fallback_context = CandidateAnalysisContext.create(
        "Ten years stated without dated roles",
        resume_json=undated_resume,
        normalized_resume=undated_normalized,
        optimized_profile=llm_profile,
    )
    assert fallback_context.candidate_experience == 12.0


@pytest.mark.asyncio
async def test_match_service_reuses_candidate_and_job_contexts(monkeypatch):
    raw_text = _structured_resume_text()
    resume_json = ResumeJsonExtractor.extract(raw_text)
    normalized = NormalizedResume.model_validate(resume_json["normalized"])
    candidate_context = CandidateAnalysisContext.create(
        cv_text=raw_text,
        resume_json=resume_json,
        normalized_resume=normalized,
        deterministic_experience=normalized.experience.deterministic_years,
    )
    job_contexts = [
        JobEvaluationContext.create({"id": "job-1", "title": "Python Developer", "department": "Engineering"}),
        JobEvaluationContext.create({"id": "job-2", "title": "API Developer", "department": "Engineering"}),
    ]
    scoring_calls: list[tuple[int, int, float | None]] = []

    monkeypatch.setattr(
        CandidateAnalysisContext,
        "create",
        classmethod(lambda cls, **kwargs: candidate_context),
    )
    monkeypatch.setattr(
        VacancyPreFilter,
        "filter_vacancies",
        classmethod(lambda cls, **kwargs: job_contexts),
    )

    def evaluate(cls, **kwargs):
        scoring_calls.append(
            (
                id(kwargs["context"]),
                id(kwargs["job"]),
                kwargs["context"].candidate_experience,
            )
        )
        return MatchService._empty_job_match().model_copy(update={"job_id": kwargs["job"].job_id})

    monkeypatch.setattr(
        "app.services.match_service.ScoringEngine.evaluate_job_match",
        classmethod(evaluate),
    )
    monkeypatch.setattr(
        "app.services.match_service.ConfigRepository.get_setting",
        lambda key, default=None: default,
    )
    llm_response = OptimizedLLMMatchResponse(
        candidate_profile=OptimizedCandidateProfile(relevant_experience_years=12.0),
        matched_vacancies=[
            OptimizedVacancyMatch(
                vacancy_id="job-1",
                semantic_reason="Python evidence supports the vacancy.",
                top_strength="The CV explicitly lists Python, directly satisfying the vacancy's Python requirement. This is the strongest documented technical match for the role.",
                main_concern="The supplied CV and vacancy do not provide enough evidence about production deployment experience. Recruiters should verify that requirement rather than infer it.",
                ai_match_explanation=(
                    "The score is supported by the direct Python evidence in both the CV and vacancy. "
                    "Missing deployment evidence limits certainty about the remaining role requirements."
                ),
                semantic_fit_score=80.0,
                classified_requirements=[
                    ClassifiedRequirementItem(requirement_id="python", description="Python", status="SATISFIED")
                ],
                evidence_snippets={
                    "python": RequirementEvidence(cv_evidence="Python", vacancy_evidence="Python Developer")
                },
            )
        ],
        active_vacancy_summary="Python vacancy evaluated.",
        ai_career_summary="Software delivery profile.",
    )
    monkeypatch.setattr(
        "app.services.match_service.OllamaLLMService.run_optimized_match",
        MagicMock(return_value=llm_response),
    )
    monkeypatch.setattr("app.services.match_service.match_result_cache_manager.get", lambda key: None)
    monkeypatch.setattr(
        "app.services.match_service.match_result_cache_manager.set",
        lambda key, value: None,
    )
    monkeypatch.setattr(settings, "LLM_SKIP_COVERAGE_THRESHOLD", 2.0)

    result = await MatchService.analyze_single_cv(
        raw_text,
        job_openings=[context.raw_job for context in job_contexts],
        resume_json=resume_json,
        normalized_resume=normalized,
        deterministic_experience=normalized.experience.deterministic_years,
    )

    assert result.normalized_resume == normalized
    assert len(scoring_calls) == 4
    assert {context_id for context_id, _, _ in scoring_calls} == {id(candidate_context)}
    assert [job_id for _, job_id, _ in scoring_calls].count(id(job_contexts[0])) == 2
    assert [job_id for _, job_id, _ in scoring_calls].count(id(job_contexts[1])) == 2
    assert {experience for _, _, experience in scoring_calls} == {2.0}
    enriched_job = next(match for match in result.unsuitable_openings if match.job_id == "job-1")
    missing_llm_job = next(match for match in result.unsuitable_openings if match.job_id == "job-2")
    assert [item.requirement_id for item in enriched_job.llm_classified_requirements] == ["python"]
    assert enriched_job.llm_evidence_snippets["python"].cv_evidence == "Python"
    assert "LLM_VACANCY_EVALUATION_MISSING" in missing_llm_job.quality_flags
    assert result.quality_metadata["missing_llm_vacancy_ids"] == 1


@pytest.mark.asyncio
async def test_match_service_does_not_reparse_supplied_resume(monkeypatch):
    resume_json = ResumeJsonExtractor.extract(_structured_resume_text())
    normalized = NormalizedResume.model_validate(resume_json["normalized"])
    monkeypatch.setattr(
        ResumeJsonExtractor,
        "extract",
        MagicMock(side_effect=AssertionError("resume reparsed")),
    )

    result = await MatchService.analyze_single_cv(
        _structured_resume_text(),
        job_openings=[],
        resume_json=resume_json,
        normalized_resume=normalized,
    )

    assert result.normalized_resume == normalized
