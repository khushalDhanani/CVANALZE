from app.repositories.processing_job import ProcessingJobRepository

for job_id in ["cvjob_0c22fc0786d40c9399263854c08a49b5ac29d9fb1fab2122834c5c754794c403", "cvjob_77a43cd16983a2c12f3b6ef3e00daa8a4dde89b926fde0dfbfc664243a38e6c9"]:
    r = ProcessingJobRepository.get(job_id)
    if r:
        print(f"Job: {r.job_id}, State: {r.state}, Progress: {r.progress}, Message: {r.message}")
    else:
        print(f"Job {job_id} not found in repository.")
