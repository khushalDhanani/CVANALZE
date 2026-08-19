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
    assert 0.0 <= ctx.taxonomy_confidence <= 1.0


def test_reciprocal_rank_fusion_service():
    job1 = JobEvaluationContext.create(
        {
            "id": "job-1",
            "title": "Backend Developer",
            "department": "Engineering",
            "required_skills": ["Python", "FastAPI"],
        }
    )
    job2 = JobEvaluationContext.create(
        {
            "id": "job-2",
            "title": "Frontend Developer",
            "department": "Engineering",
            "required_skills": ["React", "TypeScript"],
        }
    )

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
    from unittest.mock import patch
    from app.services.vacancy_prefilter import CandidateSearchContext
    
    jobs = [
        {
            "id": f"job-{i}",
            "title": "Software Developer",
            "department": "Engineering",
            "_precomputed_job_family": "Engineering",
            "_precomputed_domain": "Engineering",
            "required_skills": ["Python"],
        }
        for i in range(5)
    ]

    mock_ctx = CandidateSearchContext.create(cv_text="")
    mock_ctx.cand_domain = "Engineering"
    mock_ctx.cand_families = ["Engineering"]
    mock_ctx.taxonomy_confidence = 1.0
    with patch("app.services.vacancy_prefilter.CandidateSearchContext.create", return_value=mock_ctx):
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
    from unittest.mock import patch
    from app.services.vacancy_prefilter import CandidateSearchContext
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

    mock_ctx = CandidateSearchContext.create(cv_text=cv_text)
    mock_ctx.cand_domain = "Information Technology"
    mock_ctx.cand_families = ["IT & Software Services"]
    mock_ctx.taxonomy_confidence = 1.0
    with patch("app.services.vacancy_prefilter.CandidateSearchContext.create", return_value=mock_ctx):
        filtered = VacancyPreFilter.filter_vacancies(
            cv_text=cv_text,
            openings=jobs,
            candidate_experience=5.0,
            top_k=2,
            cv_embedding=[0.1] * 384,  # Stub embedding for test
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


def test_stage_0_known_domain_compatible_vacancies():
    from unittest.mock import patch
    from app.services.vacancy_prefilter import CandidateSearchContext
    jobs = [
        {"id": "1", "department": "Information Technology", "_precomputed_job_family": "CIS Team", "_precomputed_domain": "Information Technology"},
        {"id": "2", "department": "Finance", "_precomputed_job_family": "Finance Team", "_precomputed_domain": "Finance"},
    ]
    mock_ctx = CandidateSearchContext.create(cv_text="")
    mock_ctx.cand_domain = "Information Technology"
    mock_ctx.cand_families = ["CIS Team"]
    mock_ctx.taxonomy_confidence = 1.0
    
    with patch("app.services.vacancy_prefilter.CandidateSearchContext.create", return_value=mock_ctx):
        filtered = VacancyPreFilter.filter_vacancies(cv_text="", openings=jobs, top_k=5)
        
    assert len(filtered) == 1
    assert filtered[0]["id"] == "1"


def test_stage_0_known_domain_zero_compatible():
    from unittest.mock import patch
    from app.services.vacancy_prefilter import CandidateSearchContext
    jobs = [{"id": "1", "_precomputed_job_family": "Finance Team", "_precomputed_domain": "Finance"}]
    mock_ctx = CandidateSearchContext.create(cv_text="")
    mock_ctx.cand_domain = "Information Technology"
    mock_ctx.cand_families = ["Engineering"]
    mock_ctx.taxonomy_confidence = 1.0
    
    with patch("app.services.vacancy_prefilter.CandidateSearchContext.create", return_value=mock_ctx):
        filtered = VacancyPreFilter.filter_vacancies(cv_text="", openings=jobs, top_k=5)
        
    assert len(filtered) == 0


def test_stage_0_unknown_domain():
    from unittest.mock import patch
    from app.services.vacancy_prefilter import CandidateSearchContext
    jobs = [{"id": "1", "vac_family": "Finance Team", "vac_tax_domain": "Finance"}]
    mock_ctx = CandidateSearchContext.create(cv_text="")
    mock_ctx.cand_domain = "Unknown"
    mock_ctx.cand_families = ["Unknown"]
    mock_ctx.taxonomy_confidence = 0.0
    
    with patch("app.services.vacancy_prefilter.CandidateSearchContext.create", return_value=mock_ctx):
        filtered = VacancyPreFilter.filter_vacancies(cv_text="", openings=jobs, top_k=5)

    assert [job["id"] for job in filtered] == ["1"]


def test_stage_0_low_confidence_domain_uses_broad_fallback():
    from unittest.mock import patch

    jobs = [
        {"id": "1", "_precomputed_job_family": "CIS Team", "_precomputed_domain": "Information Technology"},
        {"id": "2", "_precomputed_job_family": "Finance Team", "_precomputed_domain": "Finance"},
    ]
    mock_ctx = CandidateSearchContext(cv_text="", cv_lower="", cv_tokens=set())
    mock_ctx.cand_domain = "Information Technology"
    mock_ctx.cand_families = ["CIS Team"]
    mock_ctx.taxonomy_confidence = 0.3

    with patch("app.services.vacancy_prefilter.CandidateSearchContext.create", return_value=mock_ctx):
        filtered = VacancyPreFilter.filter_vacancies(cv_text="", openings=jobs, top_k=5)

    assert {job["id"] for job in filtered} == {"1", "2"}


def test_ambiguous_cross_family_vacancy_survives_on_lexical_evidence():
    from unittest.mock import patch

    jobs = [
        {
            "id": "a-relevant",
            "title": "Control Engineer",
            "required_skills": ["SCADA"],
            "_precomputed_job_family": "Control & Instrumentation",
            "_precomputed_domain": "Plant Operations",
        },
        {
            "id": "z-unrelated",
            "title": "Accountant",
            "required_skills": ["Ledger"],
            "_precomputed_job_family": "Finance",
            "_precomputed_domain": "Finance",
        },
    ]
    mock_ctx = CandidateSearchContext(
        cv_text="SCADA control systems",
        cv_lower="scada control systems",
        cv_tokens={"scada", "control", "systems"},
        cand_domain="Engineering",
        cand_families=["General Engineering"],
        taxonomy_confidence=0.4,
    )

    with patch("app.services.vacancy_prefilter.CandidateSearchContext.create", return_value=mock_ctx):
        filtered = VacancyPreFilter.filter_vacancies(cv_text=mock_ctx.cv_text, openings=jobs, top_k=1)

    assert [job["id"] for job in filtered] == ["a-relevant"]


def test_vector_top_n_does_not_permanently_exclude_lexical_candidate(monkeypatch):
    from unittest.mock import patch

    jobs = [
        {
            "id": "a-lexical",
            "title": "Python Engineer",
            "required_skills": ["Python"],
            "_precomputed_job_family": "Engineering",
            "_precomputed_domain": "Technology",
        },
        {
            "id": "z-vector",
            "title": "Accountant",
            "required_skills": ["Ledger"],
            "_precomputed_job_family": "Engineering",
            "_precomputed_domain": "Technology",
        },
    ]
    mock_ctx = CandidateSearchContext(
        cv_text="Python",
        cv_lower="python",
        cv_tokens={"python"},
        cv_embedding=[0.1, 0.2],
        cand_domain="Technology",
        cand_families=["Engineering"],
        taxonomy_confidence=1.0,
    )
    monkeypatch.setattr("app.services.vacancy_prefilter.settings.EMBEDDING_ENABLED", True)
    monkeypatch.setattr(
        PgVectorQueryCache,
        "query_pgvector_cached",
        lambda *_args, **_kwargs: (("z-vector", 1, 0.1),),
    )

    with patch("app.services.vacancy_prefilter.CandidateSearchContext.create", return_value=mock_ctx):
        filtered = VacancyPreFilter.filter_vacancies(cv_text="Python", openings=jobs, top_k=1)

    assert [job["id"] for job in filtered] == ["a-lexical"]


def test_stage_0_missing_taxonomy():
    from unittest.mock import patch
    import pytest
    jobs = [{"id": "1", "vac_family": "Finance Team", "vac_tax_domain": "Finance"}]
    
    mock_ctx = CandidateSearchContext.create(cv_text="")
    
    class MockRules:
        candidate_rules = []
        canonical_domains = []
        default_family = "Unknown"
        semantic_match_threshold = 0.8
        
    with (
        patch("app.services.vacancy_prefilter.CandidateSearchContext.create", return_value=mock_ctx),
        patch("app.services.vacancy_prefilter.RuleConfigManager.get_taxonomy_rules", return_value=MockRules()),
    ):
        with pytest.raises(AnalysisUnavailableError, match="Taxonomy/configuration is unavailable"):
            VacancyPreFilter.filter_vacancies(cv_text="", openings=jobs, top_k=5)
