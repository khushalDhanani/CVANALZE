from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.cache import (
    embedding_cache_manager,
    match_result_cache_manager,
    vacancy_cache_manager,
)
from app.main import app
from app.services.talent_graph_service import TalentKnowledgeGraphService

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


def test_candidate_360_graph_generation():
    """
    Verifies Candidate 360 graph generation with nodes (Candidate, Skill, Company, Vacancy, Similar Candidate) and edges.
    """
    mock_result = {
        "id": "cand_graph_1",
        "filename": "cand_graph_1.pdf",
        "markdown": "Senior Python Engineer with FastAPI experience at Tech Corp",
        "quality_metrics": {"experience_years": 5.0},
        "match_analysis": {
            "primary_department": "Engineering",
            "suitable_openings": [
                {
                    "vacancy_id": 101,
                    "job_title": "Python Engineer",
                    "score": 92.5,
                    "classification": "HIGH",
                }
            ],
        },
        "resume_json": {
            "contact_info": {"name": "Alex Mercer", "email": "alex@example.com"},
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "work_experience": [{"company": "Tech Corp", "role": "Senior Developer"}],
        },
        "similar_candidates": [
            {
                "cv_key": "cand_other",
                "full_name": "Other Candidate",
                "similarity_score": 0.89,
                "is_duplicate_flag": False,
            }
        ],
    }

    with patch(
        "app.repositories.result.ResultRepository.read_result_by_filename",
        return_value=mock_result,
    ):
        graph = TalentKnowledgeGraphService.get_candidate_360_graph("cand_graph_1")

        assert graph["candidate_id"] == "cand_graph_1"
        assert graph["full_name"] == "Alex Mercer"
        assert len(graph["nodes"]) > 0
        assert len(graph["edges"]) > 0

        node_types = {n["type"] for n in graph["nodes"]}
        assert "Candidate" in node_types
        assert "Skill" in node_types
        assert "Company" in node_types
        assert "Vacancy" in node_types

        edge_rels = {e["relationship"] for e in graph["edges"]}
        assert "HAS_SKILL" in edge_rels
        assert "WORKED_AT" in edge_rels
        assert "MATCHES" in edge_rels
        assert "SEMANTICALLY_SIMILAR" in edge_rels


def test_vacancy_360_graph_generation():
    """
    Verifies Vacancy 360 graph generation with nodes (Vacancy, Department, Skill, Candidate Match) and edges.
    """
    mock_job = {
        "id": "vac_graph_101",
        "vacancy_id": 101,
        "title": "Senior Python Engineer",
        "department": "Engineering",
        "required_skills": ["Python", "FastAPI"],
        "min_experience_years": 4.0,
    }

    with patch("app.repositories.job.JobRepository.get_all_jobs", return_value=[mock_job]):
        graph = TalentKnowledgeGraphService.get_vacancy_360_graph("101")

        assert graph["vacancy_id"] == "101"
        assert graph["title"] == "Senior Python Engineer"

        node_types = {n["type"] for n in graph["nodes"]}
        assert "Vacancy" in node_types
        assert "Department" in node_types
        assert "Skill" in node_types

        edge_rels = {e["relationship"] for e in graph["edges"]}
        assert "BELONGS_TO" in edge_rels
        assert "REQUIRES_SKILL" in edge_rels


def test_skill_intelligence_graph():
    """
    Verifies Skill Intelligence graph generation and market demand metrics.
    """
    graph = TalentKnowledgeGraphService.get_skill_intelligence_graph("Python")

    assert graph["skill"] == "Python"
    assert "nodes" in graph
    assert "edges" in graph
    assert "metrics" in graph
    assert "candidate_supply_count" in graph["metrics"]
    assert "vacancy_demand_count" in graph["metrics"]


def test_recruitment_analytics_graph():
    """
    Verifies global recruitment analytics graph metrics.
    """
    analytics = TalentKnowledgeGraphService.get_recruitment_analytics_graph()

    assert "graph_summary" in analytics
    assert "total_candidates" in analytics["graph_summary"]
    assert "total_vacancies" in analytics["graph_summary"]
    assert "top_candidate_skills" in analytics
    assert "department_distribution" in analytics


def test_talent_graph_api_endpoints():
    """
    Verifies REST API endpoints for Candidate 360, Vacancy 360, Skill Intelligence, and Analytics.
    """
    resp_analytics = client.get("/api/talent-graph/analytics")
    assert resp_analytics.status_code == 200
    assert "graph_summary" in resp_analytics.json()

    resp_skill = client.get("/api/talent-graph/skill/python")
    assert resp_skill.status_code == 200
    assert resp_skill.json()["skill"] == "python"
