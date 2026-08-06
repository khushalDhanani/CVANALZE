from app.repositories.processing_job import ProcessingJobRepository
from app.schemas.contracts import JobState

records = ProcessingJobRepository.get_recent(limit=10)
for r in records:
    print(f"Job: {r.job_id}, State: {r.state}, Progress: {r.progress}, Message: {r.message}")
