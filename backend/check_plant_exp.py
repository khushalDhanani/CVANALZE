from app.core.database import PostgresAppSession
from app.repositories.job import JobRepository
with PostgresAppSession() as session:
    jobs = JobRepository.get_all_jobs()
    for j in jobs:
        if "Plant Assistant - I" in str(j.get("title")):
            print(f"Title: {j.get('title')}, MinExp: {j.get('min_experience_years')}, MaxExp: {j.get('max_experience_years')}")
