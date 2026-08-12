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
from app.services.dynamic_scoring_prefilter_service import DynamicScoringAndPrefilterService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cv_analyzer")
logger.setLevel(logging.INFO)

async def run():
    with PostgresAppSession() as session:
        res = session.query(CVResult).filter(CVResult.cv_key == "cv_1760668444").first()
        cv_text = res.text_content
        rj = res.resume_json if isinstance(res.resume_json, dict) else json.loads(res.resume_json)
        cv_hash = res.cv_hash
        ma = res.match_analysis if isinstance(res.match_analysis, dict) else json.loads(res.match_analysis)
        ctx = ma.get("candidate_context", {})
    
    openings = await run_in_threadpool(JobRepository.get_all_jobs)
    job_1215 = [j for j in openings if str(j.get("id")) == "1215"][0]
    
    job_ctx = JobEvaluationContext.create(job_1215)
    cand_ctx = CandidateSearchContext.create(
        cv_text=cv_text,
        candidate_experience=7.8,
        cv_embedding=None,
        resume_json=rj,
        analysis_context=None,
    )
    
    prefilter_rules = DynamicScoringAndPrefilterService.get_prefilter_rules()
    
    score = 0.0
    print("Evaluating Lexical Score for 1215:")
    if job_ctx.dept_terms:
        if any(t in cand_ctx.cv_tokens for t in job_ctx.dept_terms):
            print(" + Department Match (terms):", prefilter_rules.lexical_weights.department_match)
            score += prefilter_rules.lexical_weights.department_match
    elif job_ctx.department_lower and job_ctx.department_lower in cand_ctx.cv_lower:
        print(" + Department Match (lower):", prefilter_rules.lexical_weights.department_match)
        score += prefilter_rules.lexical_weights.department_match

    if job_ctx.title_words:
        title_matches = cand_ctx.cv_tokens.intersection(job_ctx.title_words)
        if title_matches:
            print(" + Title Term Match:", title_matches, len(title_matches) * prefilter_rules.lexical_weights.title_term_match)
            score += len(title_matches) * prefilter_rules.lexical_weights.title_term_match

    for skill in job_ctx.required_skills:
        skill_lower = skill.lower().strip()
        if not skill_lower: continue
        if " " in skill_lower or "-" in skill_lower or "/" in skill_lower:
            if skill_lower in cand_ctx.cv_lower:
                print(" + Req Skill (phrase):", skill_lower, prefilter_rules.lexical_weights.required_skill_match)
                score += prefilter_rules.lexical_weights.required_skill_match
        elif skill_lower in cand_ctx.cv_tokens:
            print(" + Req Skill (token):", skill_lower, prefilter_rules.lexical_weights.required_skill_match)
            score += prefilter_rules.lexical_weights.required_skill_match

    if cand_ctx.candidate_experience is not None:
        min_e = job_ctx.min_experience_years
        max_e = job_ctx.max_experience_years
        print(f"Cand Exp: {cand_ctx.candidate_experience}, Min: {min_e}, Max: {max_e}")
        if (min_e is None or cand_ctx.candidate_experience >= min_e) and (max_e is None or cand_ctx.candidate_experience <= max_e):
            print(" + Experience Suitability:", prefilter_rules.lexical_weights.experience_suitability)
            score += prefilter_rules.lexical_weights.experience_suitability
            
    print("Total Lexical Score:", score)

asyncio.run(run())
