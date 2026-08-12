import asyncio
from app.services.match_service import MatchService

async def main():
    software_cv = """
    Sarah Developer
    Senior Full Stack & Mobile Engineer
    Skills: Flutter, Dart, React Native, REST APIs, Python, Git
    Experience: 4 years software development
    """
    matching_vacancies = [
        {
            "id": 301,
            "vacancy_id": 301,
            "title": "Mobile App Developer",
            "department": "Information Technology",
            "department_name": "Information Technology",
            "required_skills": ["Flutter", "Dart", "REST APIs"],
            "min_experience_years": 2,
        }
    ]

    analysis = await MatchService.analyze_single_cv(
        cv_text=software_cv,
        job_openings=matching_vacancies,
        document_hash="doc_test_genuine_456",
        candidate_id="cand_test_genuine_456",
    )
    print(analysis.model_dump())
    
asyncio.run(main())
