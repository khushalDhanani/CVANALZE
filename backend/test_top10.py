import asyncio
import json
import logging
from app.core.database import PostgresAppSession
from app.models.result import CVResult
from app.services.vacancy_prefilter import VacancyPreFilter, get_candidate_embedding, CandidateSearchContext
from app.services.embedding_service import EmbeddingService
from app.repositories.job import JobRepository
from fastapi.concurrency import run_in_threadpool
from app.schemas.job_context import JobEvaluationContext

async def run():
    with PostgresAppSession() as session:
        res = session.query(CVResult).filter(CVResult.cv_key == "cv_1760668444").first()
        cv_text = res.text_content
        rj = res.resume_json if isinstance(res.resume_json, dict) else json.loads(res.resume_json)
        cv_hash = res.cv_hash

    openings = await run_in_threadpool(JobRepository.get_all_jobs)
    cv_embedding = EmbeddingService.generate_embedding(cv_text, identifier=cv_hash)
    
    job_contexts = VacancyPreFilter.filter_vacancies(
        cv_text=cv_text,
        openings=openings,
        candidate_experience=7.8,
        top_k=10, 
        cv_embedding=cv_embedding,
        resume_json=rj,
        return_contexts=True,
    )
    
    for i, j in enumerate(job_contexts):
        details = j.raw_job.get("_rrf_details", {})
        print(f"Rank {i+1}: ID={j.job_id} | Title={j.title} | Lexical={details.get('lexical_rank')} | Vector={details.get('vector_rank')} | RRF={details.get('rrf_score')}")
        
asyncio.run(run())
