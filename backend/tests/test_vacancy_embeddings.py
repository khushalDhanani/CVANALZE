import hashlib
from unittest.mock import patch

import pytest

from app.core.cache import embedding_cache_manager, vacancy_cache_manager
from app.repositories.job import JobRepository
from app.services.embedding_service import (
    EmbeddingService,
    build_vacancy_canonical_text,
    get_vacancy_embedding,
    save_vacancy_embedding,
)


@pytest.fixture(autouse=True)
def clear_caches():
    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()
    EmbeddingService.reset_metrics()
    yield
    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()
    EmbeddingService.reset_metrics()


def test_build_vacancy_canonical_text_all_fields():
    job = {
        "title": "Senior Staff Engineer",
        "department_name": "Core Platform",
        "company_name": "Acme Corp",
        "job_description": "Lead architect for cloud services and microservices.",
        "responsibilities": "Design scalable APIs, mentor engineers, oversee release cycles.",
        "required_skills": ["Python", "Go", "Kubernetes", "PostgreSQL"],
        "preferred_keywords": ["gRPC", "Kafka", "AWS"],
        "min_experience_years": 8.0,
        "max_experience_years": 12.0,
        "education": "Bachelor's degree in Computer Science or equivalent",
        "certifications": "AWS Certified Solutions Architect",
    }

    canonical = build_vacancy_canonical_text(job)

    assert "Vacancy Title: Senior Staff Engineer" in canonical
    assert "Department: Core Platform" in canonical
    assert "Company: Acme Corp" in canonical
    assert "Job Description: Lead architect for cloud services and microservices." in canonical
    assert "Responsibilities: Design scalable APIs, mentor engineers, oversee release cycles." in canonical
    assert "Required Skills: Python, Go, Kubernetes, PostgreSQL" in canonical
    assert "Preferred Keywords: gRPC, Kafka, AWS" in canonical
    assert "Experience Required: 8.0 to 12.0 years" in canonical
    assert "Education Requirements: Bachelor's degree in Computer Science or equivalent" in canonical
    assert "Certifications: AWS Certified Solutions Architect" in canonical


def test_incremental_vacancy_embedding_skips_unchanged():
    jobs = [
        {
            "id": "vac_50101",
            "vacancy_id": 50101,
            "title": "Backend Engineer",
            "department": "Engineering",
            "required_skills": ["Python", "FastAPI"],
            "job_description": "Build high throughput web APIs.",
        },
        {
            "id": "vac_50102",
            "vacancy_id": 50102,
            "title": "DevOps Specialist",
            "department": "Infrastructure",
            "required_skills": ["Docker", "Kubernetes"],
            "job_description": "Manage CI/CD pipelines.",
        },
    ]

    mock_embeddings = [
        [0.1] * 768,
        [0.2] * 768,
    ]

    with patch(
        "app.services.embedding_service.get_vacancy_embedding",
        return_value=(None, None),
    ):
        with patch(
            "app.services.embedding_service.EmbeddingService.generate_batch_embeddings",
            return_value={"0": mock_embeddings[0], "1": mock_embeddings[1]},
        ) as mock_batch:
            # First sync: Both vacancies are new -> batch embed called once for 2 items
            first_metrics = JobRepository._cache_vacancy_embeddings(jobs)
            assert mock_batch.call_count == 1
            assert len(mock_batch.call_args.args[0]) == 2
            assert first_metrics == {"total": 2, "synced": 2, "skipped": 0, "failed": 0}

        with patch("app.services.embedding_service.EmbeddingService.generate_batch_embeddings") as mock_batch_second:
            # Second sync: No content changes -> 0 vacancies uncached -> batch embed NOT called!
            second_metrics = JobRepository._cache_vacancy_embeddings(jobs)
            assert mock_batch_second.call_count == 0
            assert second_metrics == {
                "total": 2,
                "synced": 0,
                "skipped": 2,
                "failed": 0,
            }


def test_vacancy_content_change_triggers_reembedding():
    job_v1 = [
        {
            "id": "vac_201",
            "vacancy_id": 201,
            "title": "Frontend Developer",
            "department": "UI Team",
            "required_skills": ["React"],
        }
    ]

    job_v2 = [
        {
            "id": "vac_201",
            "vacancy_id": 201,
            "title": "Frontend Developer",
            "department": "UI Team",
            "required_skills": ["React", "TypeScript", "Next.js"],  # Content updated!
        }
    ]

    with patch(
        "app.services.embedding_service.EmbeddingService.generate_batch_embeddings",
        return_value={"0": [0.3] * 768},
    ) as mock_batch:
        JobRepository._cache_vacancy_embeddings(job_v1)
        assert mock_batch.call_count == 1

    with patch(
        "app.services.embedding_service.EmbeddingService.generate_batch_embeddings",
        return_value={"0": [0.4] * 768},
    ) as mock_batch_v2:
        # Second sync with updated skills -> Hash changed -> batch embed called again!
        JobRepository._cache_vacancy_embeddings(job_v2)
        assert mock_batch_v2.call_count == 1


def test_save_and_get_vacancy_embedding_cache_fallback():
    mock_vec = [0.8] * 768
    vac_id = 9999
    content_hash = hashlib.sha256(b"mock canonical text").hexdigest()

    # Save embedding
    save_vacancy_embedding(vac_id, mock_vec, content_hash=content_hash)

    # Query embedding from cache/DB
    retrieved_vec, _retrieved_hash = get_vacancy_embedding(vac_id)

    assert retrieved_vec == mock_vec
