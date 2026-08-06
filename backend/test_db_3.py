import asyncio
from app.repositories.job import JobRepository

async def main():
    jobs = JobRepository.get_all_jobs()
    print("TOTAL JOBS:", len(jobs))
    for j in jobs:
        print("JOB:", j.get("job_title"), "DEPT:", j.get("department_name") or j.get("department"))
    
if __name__ == "__main__":
    asyncio.run(main())
