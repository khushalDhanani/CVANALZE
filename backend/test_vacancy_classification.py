import asyncio
from app.services.job_taxonomy import TaxonomyClassifier
from app.schemas.domain import MatchType

job = {
    "title": "Mobile App Developer",
    "department": "Information Technology",
    "department_name": "Information Technology",
    "required_skills": ["Flutter", "Dart", "REST APIs"],
}

domain, family = TaxonomyClassifier.classify_vacancy(job, skip_vector=True)
print(f"Domain: {domain}")
print(f"Family: {family}")
