from app.services.scoring_engine import ScoringEngine
from app.schemas.job import JobOpening

job = JobOpening(
    id="995",
    title="Engineer (Process and Project)",
    department="Process & Project Team",
    required_skills=[],
    preferred_keywords=[],
    vacancy_id=995,
    department_name="Process & Project Team",
)

res = ScoringEngine.evaluate_job_match("some cv text", job.dict())
print(f"Score: {res.score}")
print(f"Coverage: {res.coverage}")
print(f"Role Score: {res.role_score}")
print(f"Skills Score: {res.skills_score}")
print(f"Experience Score: {res.experience_score}")
print(f"Domain Score: {res.domain_score}")
print(f"Classification: {res.classification}")
print(f"Recommendation: {res.recommendation}")
