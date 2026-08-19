from __future__ import annotations

import pytest
from unittest.mock import patch

from app.services.embedding_service import EmbeddingService, get_embedding
from app.services.experience_calculator import ExperienceCalculator
from app.services.match_service import MatchService
from app.services.resume_field_extractor import ResumeFieldExtractor
from app.services.resume_text_normalizer import ResumeTextNormalizer
from app.services.vacancy_prefilter import VacancyPreFilter


@pytest.mark.asyncio
async def test_end_to_end_cv_processing_pipeline(
    sample_candidate_cv_text: str,
    sample_job_openings: list[dict],
) -> None:
    # 1. Text normalization
    cleaned_text = ResumeTextNormalizer.sanitize(sample_candidate_cv_text)
    assert len(cleaned_text) > 0

    # 2. Section and field extraction
    lines = cleaned_text.splitlines()
    name, confidence, confidence_level, source = ResumeFieldExtractor.extract_candidate_name(
        lines,
        email="alex.mercer@example.com",
        phone="+1 555-019-2834",
        location="San Francisco, CA",
    )
    assert "ALEX" in name.upper()
    assert "MERCER" in name.upper()

    skills = ResumeFieldExtractor._extract_skills(lines)
    assert isinstance(skills, dict)
    assert len(skills) > 0

    # 3. Experience calculation
    resume_dict = {
        "work_experience": [
            {"job_title": "Senior Backend Developer", "company": "Tech Innovations Inc.", "dates": "June 2021 - Present"},
            {"job_title": "Software Engineer", "company": "NextGen Solutions", "dates": "July 2018 - May 2021"},
        ]
    }
    exp_calc = ExperienceCalculator.calculate_canonical_experience(resume_dict, cv_text=cleaned_text)
    assert exp_calc["total_experience_years"] >= 5.0

    # 4. Prefiltering & Match Service Analysis
    mock_embedding = [0.05] * 768
    with (
        patch.object(EmbeddingService, "generate_embedding", return_value=mock_embedding),
        patch("app.services.match_service.OllamaLLMService.run_optimized_match", return_value=None),
    ):
        cv_embedding = get_embedding(cleaned_text)
        shortlist = VacancyPreFilter.filter_vacancies(
            cv_text=cleaned_text,
            openings=sample_job_openings,
            top_k=5,
            cv_embedding=cv_embedding,
        )
        assert len(shortlist) > 0
        # The software developer job should be in the shortlist
        assert any(job["vacancy_id"] == 101 for job in shortlist)

        analysis = await MatchService.analyze_single_cv(
            cv_text=cleaned_text,
            job_openings=sample_job_openings,
            candidate_experience=exp_calc["total_experience_years"],
            document_hash="test_pipeline_doc_hash_123",
            candidate_id="cand_alex_mercer",
            cv_embedding=cv_embedding,
        )

        assert analysis is not None
        assert analysis.best_match is not None
        assert analysis.best_match.vacancy_id == 101
        assert analysis.best_match.score > 40.0
