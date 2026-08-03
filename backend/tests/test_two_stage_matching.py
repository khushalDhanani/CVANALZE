from app.services.scoring_engine import ScoringEngine


def test_mandatory_failure_reduces_score_and_requires_hr_review():
    cv_text = """
    ## Senior Python Developer
    Skills: Python, Django, REST API, Git
    Experience: 10 years of software development experience.
    """
    job = {
        "id": "job_1",
        "title": "Senior Python Developer",
        "department": "Engineering",
        "required_skills": [
            "Python",
            "Docker",
            "Kubernetes",
        ],  # Docker and Kubernetes are missing
        "preferred_keywords": ["Git", "CI/CD"],
        "min_experience_years": 5.0,
    }

    result = ScoringEngine.evaluate_job_match(cv_text, job, candidate_experience=10.0)

    # Must fail mandatory requirements for Docker and Kubernetes
    assert len(result.mandatory_failures) == 2
    assert result.hr_review_required is True
    assert result.score <= 65.0  # Capped at max score on mandatory failure
    assert result.score < 100.0
    assert "Mandatory requirement failure(s)" in result.reason

    # Dual evidence verification
    assert "req_skill_docker" in result.evidence
    ev = result.evidence["req_skill_docker"]
    assert "Docker" in ev.vacancy_evidence
    assert "missing" in ev.cv_evidence.lower()


def test_false_100_percent_prevention():
    cv_text = """
    ## Frontend Engineer
    Skills: React, JavaScript, HTML, CSS
    Experience: 4 years
    """
    job = {
        "id": "job_2",
        "title": "Frontend Engineer",
        "department": "Engineering",
        "required_skills": ["React", "JavaScript"],
        "preferred_keywords": [
            "TypeScript",
            "GraphQL",
            "Tailwind",
        ],  # Missing preferred keywords
        "min_experience_years": 2.0,
    }

    result = ScoringEngine.evaluate_job_match(cv_text, job, candidate_experience=4.0)

    # Mandatory satisfied, but preferred missing -> score must NOT be 100%
    assert len(result.mandatory_failures) == 0
    assert result.score < 100.0


def test_candidate_matching_all_explicit_requirements_scores_high():
    cv_text = """
    ## Senior React Developer
    Skills: React, JavaScript, TypeScript, GraphQL
    Experience: 6 years
    """
    job = {
        "id": "job_3",
        "title": "Senior React Developer",
        "department": "Engineering",
        "required_skills": ["React", "JavaScript"],
        "preferred_keywords": ["TypeScript", "GraphQL"],
        "min_experience_years": 5.0,
    }

    result = ScoringEngine.evaluate_job_match(cv_text, job, candidate_experience=6.0)

    assert len(result.mandatory_failures) == 0
    assert len(result.missing_criteria) == 0
    assert result.score >= 70.0
    assert result.hr_review_required is False


def test_unspecified_education_does_not_reduce_score():
    cv_text = """
    ## Self-Taught Software Developer
    Skills: Python, FastAPI, PostgreSQL
    Experience: 3 years building web apps.
    (No formal college degree listed)
    """
    job = {
        "id": "job_4",
        "title": "Backend Developer",
        "department": "Engineering",
        "required_skills": ["Python", "FastAPI"],
        "preferred_keywords": ["PostgreSQL"],
        "min_experience_years": 2.0,
        # Notice: NO education requirement in job dict
    }

    result = ScoringEngine.evaluate_job_match(cv_text, job, candidate_experience=3.0)

    # Education requirement should not be created as mandatory or reduce score
    edu_reqs = [r for r in result.mandatory_requirements if "education" in r.requirement_id.lower()]
    assert len(edu_reqs) == 0
    assert result.score >= 70.0


def test_dynamic_career_transition_detection():
    cv_text = """
    ## Lead Software Engineer
    Skills: Java, Spring Boot, Microservices, Architecture
    Current Role: Lead Software Engineer
    Experience: 8 years in Backend Engineering.
    """
    job = {
        "id": "job_5",
        "title": "Technical Product Manager",
        "department": "Product",
        "required_skills": ["Product Strategy", "Roadmapping", "Java"],
        "preferred_keywords": ["Agile", "User Research"],
        "min_experience_years": 5.0,
    }

    result = ScoringEngine.evaluate_job_match(cv_text, job, candidate_experience=8.0)

    assert result.career_transition_detected is True
    assert "career transition" in result.career_transition_note.lower()
    # Mandatory skills Product Strategy and Roadmapping are missing -> strict failure enforced
    failure_ids = {item.requirement_id for item in result.mandatory_failures}
    assert {"req_skill_product_strategy", "req_skill_roadmapping"}.issubset(failure_ids)
    assert result.hr_review_required is True


def test_dual_evidence_tracing():
    cv_text = """
    ## Registered Nurse
    Skills: Patient Care, Clinical Assessment, ICU, CPR
    Experience: 5 years in Hospital Care
    """
    job = {
        "id": "job_6",
        "title": "ICU Registered Nurse",
        "department": "Healthcare",
        "required_skills": ["Patient Care", "ICU"],
        "preferred_keywords": ["CPR"],
        "min_experience_years": 3.0,
    }

    result = ScoringEngine.evaluate_job_match(cv_text, job, candidate_experience=5.0)

    assert len(result.evidence) > 0
    for dual_ev in result.evidence.values():
        assert dual_ev.cv_evidence != ""
        assert dual_ev.vacancy_evidence != ""


def test_cross_industry_generalization():
    cv_text = """
    ## Financial Analyst
    Skills: Financial Modeling, Valuation, Excel, SQL, Forecasting
    Experience: 4 years at Investment Bank
    """
    job = {
        "id": "job_7",
        "title": "Senior Financial Analyst",
        "department": "Finance",
        "required_skills": ["Financial Modeling", "Valuation", "SQL"],
        "preferred_keywords": ["Forecasting"],
        "min_experience_years": 3.0,
    }

    result = ScoringEngine.evaluate_job_match(cv_text, job, candidate_experience=4.0)

    assert result.score == 100.0
    assert result.classification == "HIGH"
    assert len(result.mandatory_failures) == 0
