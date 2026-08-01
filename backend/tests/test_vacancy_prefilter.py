# backend/tests/test_vacancy_prefilter.py
import pytest

from app.schemas.job_context import JobEvaluationContext
from app.services.vacancy_prefilter import (
    CandidateSearchContext,
    PgVectorQueryCache,
    ReciprocalRankFusionService,
    VacancyPreFilter,
)


@pytest.fixture(autouse=True)
def clear_caches():
    PgVectorQueryCache.query_pgvector_cached.cache_clear()


def test_candidate_search_context_creation():
    cv_text = "Senior Python Software Engineer with FastAPI, PostgreSQL, and Docker experience."
    ctx = CandidateSearchContext.create(
        cv_text=cv_text,
        candidate_experience=5.0,
    )

    assert ctx.cv_text == cv_text
    assert "fastapi" in ctx.cv_tokens
    assert "postgresql" in ctx.cv_tokens
    assert ctx.candidate_experience == 5.0
    assert ctx.cand_domain is not None
    assert isinstance(ctx.cand_families, list)


def test_reciprocal_rank_fusion_service():
    job1 = JobEvaluationContext.create({
        "id": "job-1",
        "title": "Backend Developer",
        "department": "Engineering",
        "required_skills": ["Python", "FastAPI"],
    })
    job2 = JobEvaluationContext.create({
        "id": "job-2",
        "title": "Frontend Developer",
        "department": "Engineering",
        "required_skills": ["React", "TypeScript"],
    })

    lex_ranks = {"job-1": 1, "job-2": 2}
    vec_ranks = {"job-1": 2, "job-2": 1}

    fused = ReciprocalRankFusionService.fuse_ranks(
        stage1_jobs=[job1, job2],
        lex_ranks=lex_ranks,
        vec_ranks=vec_ranks,
        k_constant=60.0,
    )

    assert len(fused) == 2
    # RRF score = 1/(60+1) + 1/(60+2) = 0.01639344 + 0.01612903 = 0.03252247
    score1, details1, _j1 = fused[0]
    score2, _details2, _j2 = fused[1]

    assert abs(score1 - score2) < 1e-6  # Identical fused score
    assert details1["lexical_rank"] in (1, 2)
    assert details1["vector_rank"] in (1, 2)


def test_vacancy_prefilter_adaptive_retrieval_skip():
    jobs = [
        {
            "id": f"job-{i}",
            "title": "Software Developer",
            "department": "Engineering",
            "required_skills": ["Python"],
        }
        for i in range(5)
    ]

    # Filter with top_k=10 (limit > len(jobs))
    filtered = VacancyPreFilter.filter_vacancies(
        cv_text="Software Developer with Python skills.",
        openings=jobs,
        top_k=10,
    )

    # Adaptive retrieval skips stages and returns all 5 jobs immediately
    assert len(filtered) == 5
    assert [j["id"] for j in filtered] == [f"job-{i}" for i in range(5)]


def test_vacancy_prefilter_end_to_end_ranking():
    jobs = [
        {
            "id": "job-py",
            "title": "Senior Python Backend Engineer",
            "department": "IT & Software Services",
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "min_experience_years": 3,
        },
        {
            "id": "job-js",
            "title": "Frontend React Developer",
            "department": "IT & Software Services",
            "required_skills": ["React", "TypeScript", "Tailwind"],
            "min_experience_years": 2,
        },
        {
            "id": "job-mech",
            "title": "Plant Mechanical Maintenance Engineer",
            "department": "Plant Maintenance",
            "required_skills": ["Pumps", "Compressors", "Hydraulics"],
            "min_experience_years": 5,
        },
    ]

    cv_text = "Senior Python Engineer with 5 years of experience in FastAPI and PostgreSQL backend development."

    filtered = VacancyPreFilter.filter_vacancies(
        cv_text=cv_text,
        openings=jobs,
        candidate_experience=5.0,
        top_k=2,
    )

    assert len(filtered) <= 2
    # The Python job must be ranked first due to Stage 0 taxonomy + lexical token matching
    assert filtered[0]["id"] == "job-py"
    assert "_prefilter_score" in filtered[0]
    assert "_rrf_details" in filtered[0]


def test_single_pgvector_query_cache():
    emb = tuple([0.1] * 128)

    # First call: hits DB/cache
    res1 = PgVectorQueryCache.query_pgvector_cached(emb, top_limit=50)

    # Second call: returns cached result without querying pgvector again
    res2 = PgVectorQueryCache.query_pgvector_cached(emb, top_limit=50)

    assert res1 is res2
    cache_info = PgVectorQueryCache.query_pgvector_cached.cache_info()
    assert cache_info.hits >= 1
