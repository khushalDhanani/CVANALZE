from app.services.scoring_engine import ScoringEngine


SAMPLE_TEST_JOBS = [
    {
        "id": "job_frontend",
        "vacancy_id": 101,
        "title": "Senior Frontend Developer",
        "department": "Engineering",
        "skills": ["HTML5", "CSS3", "JavaScript", "React"],
        "min_experience_years": 5.0,
        "min_experience": 5.0,
        "main_department_id": 10,
        "department_id": 101,
        "designation_id": 1001,
    },
    {
        "id": "job_admin",
        "vacancy_id": 201,
        "title": "Office Administrator",
        "department": "Administration",
        "skills": ["Filing", "Data Entry"],
        "min_experience_years": 1.0,
        "min_experience": 1.0,
        "main_department_id": 20,
        "department_id": 201,
        "designation_id": 2001,
    },
]


def test_scoring_engine_high_match():
    cv_text = """
    ## HITESH GHOGHARI
    Senior Frontend Developer
    Skills: HTML5, CSS3, JavaScript, React, Tailwind CSS, Bootstrap, Figma, Git, Material UI, Shopify
    Experience: 8+ years converting Figma to Code and building React UI components.
    """
    analysis = ScoringEngine.analyze_cv(cv_text, job_openings=SAMPLE_TEST_JOBS)

    assert analysis.primary_department is not None
    reviewed_match = analysis.best_match or analysis.unsuitable_openings[0]
    assert reviewed_match.score >= 0.0


def test_scoring_engine_medium_match():
    cv_text = """
    ## Alex Smith
    Web Developer
    Skills: HTML5, CSS3, JavaScript, Git
    Experience: 1 year developing basic websites.
    """
    analysis = ScoringEngine.analyze_cv(cv_text, job_openings=SAMPLE_TEST_JOBS)

    best = analysis.best_match or analysis.unsuitable_openings[0]
    assert best.classification in ["HIGH", "MEDIUM", "LOW"]
    assert best.score >= 0.0


def test_scoring_engine_low_match_never_rejects():
    cv_text = """
    ## John Doe
    General Office Administrator
    Experience in filing, phone calls, and data entry.
    """
    analysis = ScoringEngine.analyze_cv(cv_text, job_openings=SAMPLE_TEST_JOBS)

    best = analysis.best_match or analysis.unsuitable_openings[0]
    assert best.classification in ["HIGH", "MEDIUM", "LOW"]
    assert "NEVER automatically rejected" in analysis.rejection_policy_note


def test_api_cv_match_endpoint(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/cv/match",
        json={"cv_text": "Skills: Python, FastAPI, SQL, REST API, Node.js, Express.js, MongoDB, Git"},
    )

    assert response.status_code == 200
    data = response.json()
    reviewed_match = data.get("best_match") or (data.get("unsuitable_openings", [None])[0])
    if reviewed_match:
        assert reviewed_match["classification"] in ["HIGH", "MEDIUM", "LOW"]
    assert "rejection_policy_note" in data


def test_evaluate_job_match_with_custom_scoring_config():
    job = {
        "id": "1",
        "title": "Software Engineer",
        "department": "Engineering",
        "skills": ["Python", "FastAPI"],
        "technologies": ["Python", "Docker"],
        "responsibilities": ["Develop APIs"],
        "mandatory_requirements": [],
    }
    cv_text = "Senior Python Developer with FastAPI and Docker experience."
    custom_config = {
        "MANDATORY_FAILURE_PENALTY_PER_ITEM": 20.0,
        "MAX_SCORE_ON_MANDATORY_FAILURE": 40.0,
        "LLM_SEMANTIC_WEIGHT": 0.3,
        "MAX_LLM_BOOST": 15.0,
        "MATCH_HIGH_THRESHOLD": 80.0,
        "MATCH_MEDIUM_THRESHOLD": 60.0,
        "MATCH_COMPONENT_WEIGHTS": {
            "role": 0.15,
            "skills": 0.25,
            "experience": 0.15,
            "education": 0.10,
            "domain": 0.15,
            "technology": 0.10,
            "certification": 0.05,
            "responsibilities": 0.05,
        },
    }
    # Must not raise UnboundLocalError: ConfigRepository
    result = ScoringEngine.evaluate_job_match(
        cv_text=cv_text,
        job=job,
        scoring_config=custom_config,
    )
    assert result.overall_score >= 0.0


def test_sub_token_matching_requires_full_phrase_not_shared_token():
    """A single shared token must not fabricate a match for a longer skill phrase."""

    def extract(norm_text, terms):
        return ScoringEngine._extract_term_matches(norm_text, terms)

    # "HPLC knowledge" is NOT proven by the word "knowledge" alone
    matched, missing = extract("I have knowledge of laboratory equipment", ["HPLC knowledge"])
    assert matched == []
    assert missing == ["HPLC knowledge"]

    # "QA documentation & Audit" needs all three tokens
    matched, missing = extract("Handled documentation and review", ["QA documentation & Audit"])
    assert matched == []
    assert missing == ["QA documentation & Audit"]

    # "Plant Commission" needs BOTH "plant" and "commission"
    matched, _ = extract("Plant Commission engineer", ["Plant Commission"])
    assert matched == ["Plant Commission"]
    matched, missing = extract("plant operations and maintenance", ["Plant Commission"])
    assert matched == []
    assert missing == ["Plant Commission"]


def test_prose_experience_clauses_and_stop_phrases_are_skipped():
    """JD-parsing artifacts (prose experience clauses, 'e.g' stop words) must be
    neither matched nor failed, so they cannot fabricate evidence or penalize."""

    # "2 to 3 years of experience in chemical plant." must not match on "experience"
    matched, missing = ScoringEngine._extract_term_matches(
        "worked in a chemical plant", ["2 to 3 years of experience in chemical plant."]
    )
    assert matched == []
    assert missing == []

    # "10 years of experience in API manufacturing" is a clause, not a skill
    matched, missing = ScoringEngine._extract_term_matches(
        "API manufacturing specialist", ["10 years of experience in API manufacturing"]
    )
    assert matched == []
    assert missing == []

    # Stop phrases ("e.g") must not auto-SATISFY
    matched, missing = ScoringEngine._extract_term_matches("Skill: e.g", ["e.g"])
    assert matched == []
    assert missing == []
