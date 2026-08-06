import pytest
from unittest.mock import patch

from app.services.match_service import MatchService
from app.services.scoring_engine import ScoringEngine

@pytest.fixture
def shadow_jobs():
    return [
        {
            "id": "job_1",
            "vacancy_id": 1,
            "title": "Senior Python Backend Engineer",
            "department": "Engineering",
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "min_experience_years": 5.0,
        },
        {
            "id": "job_2",
            "vacancy_id": 2,
            "title": "Sales Manager",
            "department": "Sales",
            "required_skills": ["B2B Sales", "CRM", "Negotiation"],
            "min_experience_years": 4.0,
        },
        {
            "id": "job_3",
            "vacancy_id": 3,
            "title": "Entry Level Developer",
            "department": "Engineering",
            "required_skills": ["Python"],
            "min_experience_years": 0.0,
        },
        {
            "id": "job_4",
            "vacancy_id": 4,
            "title": "Incomplete Vacancy",
            "department": "Operations",
            "required_skills": [],
            "min_experience_years": 0.0,
        },
    ]

cv_correct_department = """
# John Doe
## Senior Python Backend Engineer
Skills: Python, FastAPI, PostgreSQL, Docker, AWS
Experience: 6 years building backend systems.
"""

cv_wrong_department = """
# Jane Smith
## Senior Sales Manager
Skills: B2B Sales, CRM, Negotiation, Leadership
Experience: 7 years in tech sales.
"""

cv_cross_domain = """
# Bob Lee
## Data Scientist
Skills: Python, Machine Learning, Data Engineering, Pandas, SQL
Experience: 4 years as Data Scientist.
"""

cv_fresher = """
# Alice Fresher
## Junior Developer
Skills: Python, HTML, CSS
Experience: 0 years, recent graduate from CS.
"""

cv_incomplete = """
# Unknown Candidate
Contact: unknown@email.com
"""

cv_no_suitable = """
# Clara Nurse
## Registered Nurse
Skills: Patient Care, CPR, Clinical Assessment
Experience: 5 years in Hospital Care
"""

@pytest.mark.asyncio
async def test_shadow_validation_correct_department(shadow_jobs):
    mock_emb = [0.1] * 768
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb), \
         patch("app.services.match_service.OllamaLLMService.run_optimized_match", return_value=None):
        
        # New Pipeline
        new_analysis = await MatchService.analyze_single_cv(
            cv_text=cv_correct_department,
            job_openings=shadow_jobs,
            cv_embedding=mock_emb,
        )
        assert new_analysis.best_match is not None
        assert new_analysis.best_match.vacancy_id == 1

        # Old Pipeline
        old_analysis = ScoringEngine.evaluate_job_match(cv_correct_department, shadow_jobs[0], candidate_experience=6.0)
        assert old_analysis.classification == "HIGH"

@pytest.mark.asyncio
async def test_shadow_validation_wrong_department(shadow_jobs):
    mock_emb = [0.1] * 768
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb), \
         patch("app.services.match_service.OllamaLLMService.run_optimized_match", return_value=None):
        
        new_analysis = await MatchService.analyze_single_cv(
            cv_text=cv_wrong_department,
            job_openings=shadow_jobs,
            cv_embedding=mock_emb,
        )
        assert new_analysis.best_match is not None
        assert new_analysis.best_match.vacancy_id == 2

        old_analysis_wrong = ScoringEngine.evaluate_job_match(cv_wrong_department, shadow_jobs[0], candidate_experience=7.0)
        assert old_analysis_wrong.classification in ["LOW", "NO_MATCH"]

@pytest.mark.asyncio
async def test_shadow_validation_cross_domain(shadow_jobs):
    mock_emb = [0.1] * 768
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb), \
         patch("app.services.match_service.OllamaLLMService.run_optimized_match", return_value=None):
        
        new_analysis = await MatchService.analyze_single_cv(
            cv_text=cv_cross_domain,
            job_openings=shadow_jobs,
            cv_embedding=mock_emb,
        )
        
        # Will likely match job_1 (Python) but maybe lower score
        old_analysis = ScoringEngine.evaluate_job_match(cv_cross_domain, shadow_jobs[0], candidate_experience=4.0)
        assert old_analysis.score >= 0.0

@pytest.mark.asyncio
async def test_shadow_validation_freshers(shadow_jobs):
    mock_emb = [0.1] * 768
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb), \
         patch("app.services.match_service.OllamaLLMService.run_optimized_match", return_value=None):
        
        new_analysis = await MatchService.analyze_single_cv(
            cv_text=cv_fresher,
            job_openings=shadow_jobs,
            cv_embedding=mock_emb,
        )
        assert new_analysis.best_match is not None
        assert new_analysis.best_match.vacancy_id == 3

        old_analysis = ScoringEngine.evaluate_job_match(cv_fresher, shadow_jobs[2], candidate_experience=0.0)
        assert old_analysis.score >= 0.0

@pytest.mark.asyncio
async def test_shadow_validation_incomplete_cv(shadow_jobs):
    mock_emb = [0.1] * 768
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb), \
         patch("app.services.match_service.OllamaLLMService.run_optimized_match", return_value=None):
        
        new_analysis = await MatchService.analyze_single_cv(
            cv_text=cv_incomplete,
            job_openings=shadow_jobs,
            cv_embedding=mock_emb,
        )
        
        # Old pipeline
        old_analysis = ScoringEngine.evaluate_job_match(cv_incomplete, shadow_jobs[0], candidate_experience=0.0)
        assert old_analysis.classification == "LOW"

@pytest.mark.asyncio
async def test_shadow_validation_incomplete_vacancy(shadow_jobs):
    mock_emb = [0.1] * 768
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb), \
         patch("app.services.match_service.OllamaLLMService.run_optimized_match", return_value=None):
        
        # Test candidate against the incomplete vacancy
        new_analysis = await MatchService.analyze_single_cv(
            cv_text=cv_correct_department,
            job_openings=[shadow_jobs[3]],
            cv_embedding=mock_emb,
        )
        
        old_analysis = ScoringEngine.evaluate_job_match(cv_correct_department, shadow_jobs[3], candidate_experience=6.0)
        assert old_analysis.score >= 0.0

@pytest.mark.asyncio
async def test_shadow_validation_no_suitable_vacancy(shadow_jobs):
    mock_emb = [0.1] * 768
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb), \
         patch("app.services.match_service.OllamaLLMService.run_optimized_match", return_value=None):
        
        new_analysis = await MatchService.analyze_single_cv(
            cv_text=cv_no_suitable,
            job_openings=shadow_jobs,
            cv_embedding=mock_emb,
        )
        assert new_analysis.best_match is None or new_analysis.best_match.overall_score < 70.0
        
        old_analysis = ScoringEngine.evaluate_job_match(cv_no_suitable, shadow_jobs[0], candidate_experience=5.0)
        assert old_analysis.classification == "LOW"
