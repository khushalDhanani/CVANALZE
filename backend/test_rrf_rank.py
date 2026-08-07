import asyncio
import json
import logging
import uuid
from app.core.database import PostgresAppSession
from app.models.result import CVResult
from app.services.vacancy_prefilter import VacancyPreFilter, get_candidate_embedding
from app.repositories.job import JobRepository
from fastapi.concurrency import run_in_threadpool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cv_analyzer")
logger.setLevel(logging.INFO)

async def run():
    with PostgresAppSession() as session:
        res = session.query(CVResult).filter(CVResult.cv_key == "cv_1760668444").first()
        cv_text = res.text_content
        rj = res.resume_json if isinstance(res.resume_json, dict) else json.loads(res.resume_json)
        cv_hash = res.cv_hash

    openings = await run_in_threadpool(JobRepository.get_all_jobs)
    
    from app.services.embedding_service import EmbeddingService
    cv_embedding = EmbeddingService.generate_embedding(cv_text, identifier=cv_hash)
    
    from app.services.vacancy_prefilter import PgVectorQueryCache
    vec_results = PgVectorQueryCache.query_pgvector_cached(tuple(cv_embedding), top_limit=200)
    for r, (vid, rank, dist) in enumerate(vec_results):
        if str(vid) == "1215":
            print(f"1215 PGVECTOR RANK: {rank}, DIST: {dist}")
            break
    
    # Run with large top_k so we can see all ranks
    job_contexts = VacancyPreFilter.filter_vacancies(
        cv_text=cv_text,
        openings=openings,
        candidate_experience=7.8,
        top_k=100, 
        cv_embedding=cv_embedding,
        resume_json=rj,
        return_contexts=True,
    )
    
    found = False
    for i, j in enumerate(job_contexts):
        if str(j.job_id) == "1215":
            print(f"\n---> 1215 found at FINAL RANK {i+1}!")
            print(f"RRF Details: {j._rrf_details}")
            found = True
            
    if not found:
        print("\n---> 1215 NOT FOUND EVEN IN TOP 100")
        
asyncio.run(run())
