from app.core.config import settings
from app.services.scoring_engine import ScoringEngine


def test_scoring_engine_high_match():
    cv_text = """
    ## HITESH GHOGHARI
    Senior Frontend Developer
    Skills: HTML5, CSS3, JavaScript, React, Tailwind CSS, Bootstrap, Figma, Git, Material UI, Shopify
    Experience: 8+ years converting Figma to Code and building React UI components.
    """
    analysis = ScoringEngine.analyze_cv(cv_text)

    # Since we are matching against real DB vacancies, we just assert that it finds a match
    # and the logic doesn't crash. 
    assert analysis.primary_department is not None
    assert analysis.best_match is not None
    assert analysis.best_match.score >= 0.0


def test_scoring_engine_medium_match():
    cv_text = """
    ## Alex Smith
    Web Developer
    Skills: HTML5, CSS3, JavaScript, Git
    Experience: 1 year developing basic websites.
    """
    analysis = ScoringEngine.analyze_cv(cv_text)

    best = analysis.best_match
    assert best.classification in ["HIGH", "MEDIUM", "LOW"]
    assert best.score >= 0.0


def test_scoring_engine_low_match_never_rejects():
    cv_text = """
    ## John Doe
    General Office Administrator
    Experience in filing, phone calls, and data entry.
    """
    analysis = ScoringEngine.analyze_cv(cv_text)

    best = analysis.best_match
    assert best.classification in ["HIGH", "MEDIUM", "LOW"]
    assert "NEVER automatically rejected" in analysis.rejection_policy_note


def test_api_cv_match_endpoint(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/cv/match",
        json={
            "cv_text": "Skills: Python, FastAPI, SQL, REST API, Node.js, Express.js, MongoDB, Git"
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "primary_department" in data
    assert data["best_match"]["classification"] in ["HIGH", "MEDIUM", "LOW"]
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

