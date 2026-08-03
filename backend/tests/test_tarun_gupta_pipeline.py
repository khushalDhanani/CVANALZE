from unittest.mock import patch

import pytest

from app.services.embedding_service import EmbeddingService, get_embedding
from app.services.match_service import MatchService
from app.services.vacancy_prefilter import VacancyPreFilter

TARUN_GUPTA_CV_TEXT = """
Tarun Gupta
Software Engineer | Flutter Mobile Developer

SKILLS
- Flutter, Dart, Firebase, REST APIs, iOS, Android

EXPERIENCE
Flutter Developer, Tech Solutions Inc (2021 - Present)
- Developed and maintained cross-platform mobile apps using Flutter.

EDUCATION
B.Tech in Computer Science (2020)
"""


@pytest.mark.asyncio
async def test_tarun_gupta_flutter_retrieval_and_ranking_with_external_systems_mocked():
    openings = [
        {
            "id": "1065",
            "vacancy_id": 1065,
            "title": "Flutter Developer",
            "department": "Engineering",
            "required_skills": ["Flutter", "Dart", "REST APIs"],
            "preferred_keywords": ["Firebase"],
            "min_experience_years": 2.0,
        },
        {
            "id": "2001",
            "vacancy_id": 2001,
            "title": "Plant Maintenance Executive",
            "department": "Operations",
            "required_skills": ["Preventive Maintenance", "Switchgear"],
            "min_experience_years": 2.0,
        },
    ]
    mock_embedding = [0.1] * 768

    with (
        patch.object(EmbeddingService, "generate_embedding", return_value=mock_embedding),
        patch(
            "app.services.match_service.OllamaLLMService.run_optimized_match",
            return_value=None,
        ),
    ):
        cv_embedding = get_embedding(TARUN_GUPTA_CV_TEXT)
        shortlist = VacancyPreFilter.filter_vacancies(
            cv_text=TARUN_GUPTA_CV_TEXT,
            openings=openings,
            top_k=5,
            cv_embedding=cv_embedding,
        )
        analysis = await MatchService.analyze_single_cv(
            cv_text=TARUN_GUPTA_CV_TEXT,
            job_openings=openings,
            candidate_experience=5.0,
            document_hash="tarun_gupta_test_hash",
            candidate_id="tarun_gupta",
            cv_embedding=cv_embedding,
        )

    assert any("flutter" in job["title"].lower() for job in shortlist)
    assert analysis.best_match.vacancy_id == 1065
    assert any(match.vacancy_id == 1065 for match in analysis.suitable_openings)
