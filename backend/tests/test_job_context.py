from app.schemas.job_context import JobEvaluationContext
from app.services.scoring_engine import ScoringEngine


def test_job_evaluation_context_creation(monkeypatch):
    from app.services.job_taxonomy import TaxonomyClassifier
    monkeypatch.setattr(TaxonomyClassifier, 'classify_vacancy', lambda *args, **kwargs: ('IT & Software Services', 'Software Engineering'))
    job_dict = {
        "id": "job_101",
        "title": "Senior Software Engineer",
        "department_name": "CIS Team",
        "required_skills": ["Software Development", "Python", "FastAPI", "Docker"],
        "preferred_keywords": ["Kubernetes", "PostgreSQL"],
        "min_experience_years": 3.0,
        "max_experience_years": 8.0,
        "max_ctc": 150000.0,
        "technologies": ["Python", "Docker"],
        "responsibilities": ["Build scalable APIs", "Maintain microservices"],
    }

    ctx = JobEvaluationContext.create(job_dict)

    assert ctx.job_id == "job_101"
    assert ctx.title == "Senior Software Engineer"
    assert ctx.title_lower == "senior software engineer"
    assert "software" in ctx.title_words
    assert "senior" not in ctx.title_words  # noise stripped
    assert ctx.department == "CIS Team"
    assert "cis" in ctx.dept_terms or "team" in ctx.dept_terms
    assert ctx.has_software_req is True
    assert ctx.is_non_it_job is False
    assert ctx.vac_tax_domain == "IT & Software Services"


def test_job_evaluation_context_from_jobs():
    jobs = [
        {"id": "j1", "title": "DevOps Engineer", "department_name": "CIS Team"},
        {
            "id": "j2",
            "title": "Mechanical Technician",
            "department_name": "Maintenance Team",
        },
    ]
    contexts = JobEvaluationContext.from_jobs(jobs)

    assert len(contexts) == 2
    assert contexts[0].job_id == "j1"
    assert contexts[1].job_id == "j2"
    assert contexts[1].is_non_it_job is True


def test_scoring_engine_parity_with_job_context():
    cv_text = """
    ## Senior Python Developer
    Skills: Python, FastAPI, Docker, PostgreSQL, REST API
    Experience: 5 years developing cloud services.
    Education: BS Computer Science
    """

    job_dict = {
        "id": "job_202",
        "title": "Backend Python Engineer",
        "department_name": "CIS Team",
        "required_skills": ["Python", "FastAPI"],
        "preferred_keywords": ["Docker"],
        "min_experience_years": 3.0,
    }

    res_raw = ScoringEngine.evaluate_job_match(cv_text, job_dict, candidate_experience=5.0)

    job_ctx = JobEvaluationContext.create(job_dict)
    res_ctx = ScoringEngine.evaluate_job_match(cv_text, job_ctx, candidate_experience=5.0)

    assert res_raw.score == res_ctx.score
    assert res_raw.classification == res_ctx.classification
    assert res_raw.matched_skills == res_ctx.matched_skills
    assert res_raw.role_score == res_ctx.role_score
