from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch

from app.schemas.candidate_search import CandidateSearchRequest
from app.services.candidate_search_service import CandidateSearchService
from app.services.candidate_vector_extractor import CandidateVectorTextExtractor
from app.services.embedding_service import (
    EmbeddingService,
    generate_candidate_multi_vector_embeddings,
    get_candidate_multi_vectors,
    save_candidate_embedding,
)


def test_candidate_vector_text_extractor_builds_all_sections():
    markdown_text = """
    # Jane Doe - Senior Software Engineer
    Location: San Francisco, CA
    Email: jane.doe@example.com

    ## Summary
    Experienced Lead Engineer with 8+ years building cloud-native microservices and distributed data pipelines.

    ## Technical Skills
    Python, FastAPI, PostgreSQL, Kubernetes, Docker, Redis, AWS, System Architecture.

    ## Work Experience
    ### Lead Software Engineer at Acme Corp (2020 - Present)
    - Architected high-throughput microservices handling 50k req/sec.
    - Designed vector similarity search pipeline on pgvector.

    ## Projects
    ### OpenSource Vector Engine
    Built a custom HNSW indexing wrapper in C++ and Python.
    """

    resume_json = {
        "contact_info": {"name": "Jane Doe", "email": "jane.doe@example.com", "job_title": "Lead Software Engineer"},
        "summary": "Experienced Lead Engineer with 8+ years building cloud-native microservices.",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Kubernetes", "Docker", "Redis", "AWS"],
        "work_experience": [
            {
                "job_title": "Lead Software Engineer",
                "company": "Acme Corp",
                "duration": "2020 - Present",
                "responsibilities": ["Architected high-throughput microservices", "Designed vector similarity search"],
            }
        ],
        "projects": [
            {
                "title": "OpenSource Vector Engine",
                "description": "Built a custom HNSW indexing wrapper",
                "technologies": ["C++", "Python"],
            }
        ],
    }

    domain_profile = {
        "recommended_department": "Engineering & Technology",
        "professional_domain": "Software Engineering",
        "strengths": ["Core Skills: Python, FastAPI", "Project Experience: 1 documented project"],
        "suitable_job_roles": ["Lead Software Engineer", "Backend Architect"],
    }

    sections = CandidateVectorTextExtractor.build_section_texts(markdown_text, resume_json, domain_profile)

    assert "profile" in sections
    assert "skills" in sections
    assert "experience" in sections
    assert "projects" in sections
    assert "domain" in sections
    assert "overall" in sections

    assert "Jane Doe" in sections["profile"] or "Lead Software Engineer" in sections["profile"]
    assert "Python" in sections["skills"]
    assert "Acme Corp" in sections["experience"]
    assert "OpenSource Vector Engine" in sections["projects"]
    assert "Engineering & Technology" in sections["domain"] or "Software Engineering" in sections["domain"]


def test_generate_candidate_multi_vector_embeddings_calls_batch_embed():
    markdown_text = "# John Doe\nSkills: Python, Go\nExperience: Backend Developer at Tech Co"
    dummy_vec = [0.1] * 768

    fake_batch_res = {
        "0": dummy_vec,  # overall
        "1": dummy_vec,  # profile
        "2": dummy_vec,  # skills
        "3": dummy_vec,  # experience
        "4": dummy_vec,  # projects
        "5": dummy_vec,  # domain
    }

    with patch.object(EmbeddingService, "generate_batch_embeddings", return_value=fake_batch_res) as mock_batch:
        multi_vecs = generate_candidate_multi_vector_embeddings("cv_test_123", markdown_text)

        assert mock_batch.called
        assert "overall" in multi_vecs
        assert "skills" in multi_vecs
        assert "experience" in multi_vecs
        assert len(multi_vecs["skills"]) == 768


def test_save_and_retrieve_candidate_multi_vectors_mocked_db():
    fake_rec = MagicMock()
    fake_rec.embedding = [0.1] * 768
    fake_rec.profile_embedding = [0.2] * 768
    fake_rec.skills_embedding = [0.3] * 768
    fake_rec.experience_embedding = [0.4] * 768
    fake_rec.projects_embedding = [0.5] * 768
    fake_rec.domain_embedding = [0.6] * 768

    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = fake_rec

    mock_session = MagicMock()
    mock_session.query.return_value = mock_query

    with patch("app.core.database.PostgresAppSession", return_value=mock_session):
        multi_vecs = get_candidate_multi_vectors("cv_key_456")

        assert "overall" in multi_vecs
        assert "profile" in multi_vecs
        assert "skills" in multi_vecs
        assert "experience" in multi_vecs
        assert "projects" in multi_vecs
        assert "domain" in multi_vecs
        assert multi_vecs["skills"][0] == 0.3


def test_candidate_search_request_schema_supports_multi_vector_fields():
    req = CandidateSearchRequest(
        query="Senior Python Developer",
        search_section="skills",
        section_weights={"skills": 0.5, "experience": 0.5},
    )
    assert req.search_section == "skills"
    assert req.section_weights["skills"] == 0.5
