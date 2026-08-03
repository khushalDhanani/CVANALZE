import pytest
from fastapi.testclient import TestClient

from app.core.cache import (
    embedding_cache_manager,
    match_result_cache_manager,
    vacancy_cache_manager,
)
from app.main import app
from app.services.domain_embedding_service import DomainEmbeddingService
from app.services.scoring_engine import ScoringEngine

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_caches():
    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()
    match_result_cache_manager.clear()
    yield
    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()
    match_result_cache_manager.clear()


def test_domain_categories_supported():
    """
    Verifies all 8 domain categories are supported by DomainEmbeddingService.
    """
    categories = DomainEmbeddingService.CATEGORIES
    expected = {
        "skills",
        "job_titles",
        "departments",
        "technologies",
        "certifications",
        "education_domains",
        "industries",
        "functional_areas",
    }
    assert expected.issubset(categories)


def test_semantic_equivalent_skills_resolution():
    """
    Verifies canonical and vector equivalent skill resolution (e.g. Postgres -> PostgreSQL, K8s -> Kubernetes).
    """
    equivalents_pg = DomainEmbeddingService.find_semantic_equivalents(term="postgres", category="skills")
    terms_pg = [e["term"] for e in equivalents_pg]
    assert "postgresql" in terms_pg

    equivalents_k8s = DomainEmbeddingService.find_semantic_equivalents(term="k8s", category="skills")
    terms_k8s = [e["term"] for e in equivalents_k8s]
    assert "kubernetes" in terms_k8s


def test_skill_expansion_with_equivalents():
    """
    Verifies expanding candidate/vacancy skills list with semantically equivalent terms.
    """
    skills = ["Postgres", "React.js", "K8s"]
    expanded = DomainEmbeddingService.expand_skills_with_semantic_equivalents(skills)

    assert "postgresql" in expanded
    assert "react" in expanded
    assert "kubernetes" in expanded


def test_deterministic_mandatory_requirement_authority_preserved():
    """
    Verifies that while domain embeddings expand skill understanding,
    deterministic validation remains the strict source of truth for mandatory failures.
    """
    cv_text = "Experienced Developer with Python experience."
    job = {
        "id": "vac_501",
        "vacancy_id": 501,
        "title": "Senior Rust Engineer",
        "department": "Engineering",
        "required_skills": ["Rust"],  # Candidate lacks Rust
        "min_experience_years": 3.0,
    }

    match_result = ScoringEngine.evaluate_job_match(cv_text=cv_text, job=job)

    # Mandatory requirement "Rust" failed -> mandatory failure penalty enforced
    assert len(match_result.mandatory_failures) > 0
    assert match_result.score <= 65.0  # Capped at MAX_SCORE_ON_MANDATORY_FAILURE


def test_domain_knowledge_categories_api():
    """
    Verifies GET /api/domain-knowledge/categories API endpoint.
    """
    resp = client.get("/api/domain-knowledge/categories")
    assert resp.status_code == 200
    cats = resp.json()
    assert isinstance(cats, list)
    assert "skills" in cats
    assert "job_titles" in cats


def test_domain_knowledge_equivalents_api():
    """
    Verifies POST /api/domain-knowledge/equivalents API endpoint.
    """
    resp = client.post(
        "/api/domain-knowledge/equivalents",
        json={"term": "postgres", "category": "skills", "threshold": 0.8},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["term"] == "postgres"
    assert data["category"] == "skills"
    assert isinstance(data["equivalents"], list)
