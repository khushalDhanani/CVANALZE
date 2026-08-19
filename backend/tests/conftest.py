from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Generator

import pytest
from starlette.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.embedding_service import EmbeddingService
from app.services.ollama_transport import OllamaTransport


@pytest.fixture(autouse=True)
def isolate_processing_job_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unit tests off the durable PostgreSQL ledger and shared processing-job caches."""
    from app.core.cache import MemoryCache, processing_job_cache_manager
    from app.repositories import processing_job as processing_job_repository_module

    monkeypatch.setattr(processing_job_repository_module, "PostgresAppSession", None)
    monkeypatch.setattr(processing_job_cache_manager, "_providers", [MemoryCache(max_size=1000)])
    monkeypatch.setattr(processing_job_repository_module.ProcessingJobRepository, "_legacy_backfill_attempted", False)


@pytest.fixture(autouse=True)
def isolate_ollama_transport(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Keep every ordinary test offline, serialized, and free of shared clients."""
    OllamaTransport.close()
    live_enabled = os.environ.get("OLLAMA_LIVE_TESTS_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    monkeypatch.setattr(settings, "OLLAMA_LIVE_TESTS_ENABLED", live_enabled)
    monkeypatch.setattr(settings, "OLLAMA_LOCK_FILE", Path(tempfile.gettempdir()) / "cv-analyzer-pytest-ollama.lock")
    monkeypatch.setattr(settings, "OLLAMA_LOCK_TIMEOUT_SECONDS", 1.0)
    yield
    OllamaTransport.close()
    EmbeddingService._failed_models_cache.clear()


@pytest.fixture(autouse=True)
def mock_rule_config_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests always have a loaded rule config since the fallback was removed from runtime."""
    from datetime import datetime, timezone
    from types import MappingProxyType

    from app.core.rule_config_manager import RuleConfigManager, UnifiedRuleConfig
    from tests.mock_rule_config import MOCK_RULE_CONFIG

    def mocked_load_config(cls: type[RuleConfigManager], candidate_dict: dict[str, Any] | None = None, tenant_id: str | None = None) -> UnifiedRuleConfig:
        raw_data = candidate_dict if candidate_dict is not None else MOCK_RULE_CONFIG
        candidate_config = UnifiedRuleConfig.model_validate(raw_data)
        cls._run_synthetic_smoke_tests(candidate_config)
        candidate_cache, compiled_pattern_count = cls._build_and_validate_all_caches(candidate_config)

        with cls._lock:
            tenant_key = tenant_id or "GLOBAL"
            cls._active_configs[tenant_key] = candidate_config
            cls._caches[tenant_key] = candidate_cache
            cls._load_counter += 1
            cls._metrics = MappingProxyType(
                {
                    "config_version": candidate_config.version,
                    "config_load_count": cls._load_counter,
                    "config_load_time_ms": 1.0,
                    "cache_build_time_ms": 1.0,
                    "compiled_pattern_count": compiled_pattern_count,
                    "configuration_size_bytes": len(str(raw_data)),
                    "last_loaded_timestamp": datetime.now(timezone.utc).isoformat(),
                    "file_hash": getattr(candidate_config, "version", "mock"),
                }
            )
        return candidate_config

    monkeypatch.setattr(RuleConfigManager, "load_config", classmethod(mocked_load_config))
    RuleConfigManager.load_config()


@pytest.fixture(autouse=True)
def mock_department_domain_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests always have taxonomy domains without requiring a live MSSQL/PG database."""
    from app.repositories.department_domain import DepartmentDomainRepository
    from app.schemas.domain import DepartmentDomain

    def mocked_load_from_db(self: DepartmentDomainRepository) -> list[DepartmentDomain]:
        return [
            DepartmentDomain(
                id=1,
                department_id=9,
                department_name="CIS Team",
                domain_name="Information Technology & Software",
                keywords=[
                    "developer",
                    "flutter",
                    "dotnet",
                    "full stack",
                    "ui/ux",
                    "desktop support",
                    "software engineer",
                    "machine learning",
                    {"term": "IT", "match_type": "CASE_SENSITIVE_ACRONYM", "weight": 1.0},
                    "network",
                    "server",
                    "infrastructure",
                ],
                default_roles=["Software Developer"],
                priority=1,
            ),
            DepartmentDomain(
                id=2,
                department_id=8,
                department_name="Finance Team",
                domain_name="Finance & Accounting",
                keywords=["finance", "tally", "ledger", "valuation"],
                default_roles=["Finance Executive"],
                priority=2,
            ),
            DepartmentDomain(
                id=3,
                department_id=7,
                department_name="Engineering Team",
                domain_name="Engineering",
                keywords=["civil", "mechanical", "engineering"],
                default_roles=["Engineer"],
                priority=3,
            ),
            DepartmentDomain(id=4, department_id=4, department_name="Sales", domain_name="Sales", keywords=["sales"], default_roles=[], priority=4),
            DepartmentDomain(id=5, department_id=5, department_name="HR", domain_name="HR", keywords=["hr"], default_roles=[], priority=5),
            DepartmentDomain(id=6, department_id=6, department_name="Operations", domain_name="Operations", keywords=["operations"], default_roles=[], priority=6),
            DepartmentDomain(id=7, department_id=7, department_name="Legal", domain_name="Legal", keywords=["legal"], default_roles=[], priority=7),
            DepartmentDomain(id=8, department_id=8, department_name="Other", domain_name="Other", keywords=["other"], default_roles=[], priority=8),
            DepartmentDomain(
                id=9,
                department_id=29,
                department_name="QA Team",
                domain_name="Quality Assurance",
                keywords=["quality assurance", "qa", "validation", "audit", "test cases"],
                default_roles=["QA Manager"],
                priority=1,
            ),
        ]

    monkeypatch.setattr(DepartmentDomainRepository, "_load_from_db", mocked_load_from_db)


@pytest.fixture(autouse=True)
def mock_prompt_service(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if request.module and "test_llm_and_prompt_service" in request.module.__name__:
        return

    from app.services.prompt_service import PromptReadiness, PromptService, ResolvedPrompt

    monkeypatch.setattr(
        PromptService,
        "_fetch_prompt_from_db",
        classmethod(lambda cls, prompt_name, tenant_id, model, target_schema, language, environment: "NO_SUITABLE_MATCH recommended_department MUST be selected from EVIDENCE CITATION"),
    )
    monkeypatch.setattr(
        PromptService,
        "get_prompt_with_version",
        classmethod(lambda _cls, prompt_name, placeholders, **kwargs: ResolvedPrompt("SAFE TEST PROMPT", "test-prompt-v1")),
    )
    monkeypatch.setattr(PromptService, "get_active_prompt_version", classmethod(lambda _cls, *args, **kwargs: "test-prompt-v1"))
    monkeypatch.setattr(PromptService, "get_active_prompt_identity", classmethod(lambda _cls, *args, **kwargs: "test-prompt-v1:test-hash"))
    monkeypatch.setattr(
        PromptService,
        "check_required_optimized_match_prompt",
        classmethod(lambda _cls: PromptReadiness(True, "READY")),
    )


@pytest.fixture(autouse=True)
def cleanup_test_cv_results() -> Generator[None, None, None]:
    """Ensure test runs do not leave mock candidate records in the active database or cache."""
    yield
    try:
        from app.core.cache import cv_result_cache_manager
        from app.core.database import PostgresAppSession
        from app.models.result import CVResult

        if PostgresAppSession is not None:
            with PostgresAppSession() as db:
                test_rows = db.query(CVResult).filter(
                    (CVResult.cv_key.ilike("%test%")) | (CVResult.cv_key.ilike("%candidate%")) | (CVResult.full_name == "Jane Doe") | (CVResult.full_name == "John Doe")
                ).all()
                if test_rows:
                    for r in test_rows:
                        db.delete(r)
                    db.commit()
        cv_result_cache_manager.clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def disable_mssql_readonly_enforcement(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure test suite does not fail on startup when running against local dev database without restricted credentials."""
    monkeypatch.setattr(settings, "MSSQL_READONLY_ENFORCEMENT", False)
    monkeypatch.setattr("app.core.lifecycle.verify_mssql_readonly", lambda: None)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI TestClient for API endpoints testing."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def recruiter_auth_headers() -> dict[str, str]:
    """Authentication headers for Recruiter tier requests."""
    key = settings.RECRUITER_API_KEYS[0] if settings.RECRUITER_API_KEYS else "test_recruiter_key_123"
    return {"Authorization": f"Bearer {key}", "X-API-Key": key}


@pytest.fixture
def admin_auth_headers() -> dict[str, str]:
    """Authentication headers for Administrator tier requests."""
    key = settings.ADMINISTRATOR_API_KEYS[0] if settings.ADMINISTRATOR_API_KEYS else "test_admin_key_123"
    return {"Authorization": f"Bearer {key}", "X-API-Key": key}


@pytest.fixture
def sample_candidate_cv_text() -> str:
    """Standard multi-section CV text fixture with dynamic, well-formatted structured content."""
    return """
Alex Mercer
Senior Software Engineer | Full Stack & Cloud Developer
Email: alex.mercer@example.com | Phone: +1 555-019-2834 | Location: San Francisco, CA

SUMMARY
Experienced software engineer with 6+ years of expertise in designing and building distributed backend systems, RESTful APIs, and cloud services using Python, FastAPI, Docker, and PostgreSQL.

SKILLS
- Programming: Python, TypeScript, Go, SQL
- Frameworks: FastAPI, Django, React, Node.js
- Databases & Tools: PostgreSQL, Redis, Docker, Kubernetes, Git, AWS (S3, ECS, Lambda)

WORK EXPERIENCE
Senior Backend Developer | Tech Innovations Inc. | San Francisco, CA
June 2021 - Present (2024)
- Architected high-throughput microservices handling 10M+ daily requests using FastAPI and Redis caching.
- Reduced database query latency by 45% through pgvector indexing and PostgreSQL query optimization.
- Led a team of 4 junior developers and established CI/CD pipelines using GitHub Actions and Docker.

Software Engineer | NextGen Solutions | San Jose, CA
July 2018 - May 2021
- Developed RESTful API endpoints for financial data processing.
- Implemented real-time event streaming using Redis pub/sub and background workers.
- Maintained 99.9% uptime for core authentication and transaction services.

EDUCATION
Bachelor of Science in Computer Science
University of California, Berkeley (2014 - 2018)

PROJECTS
- Distributed Cache Engine: Built an in-memory key-value cache with LRU eviction and replication support.
- Smart Job Matcher: Built an open-source NLP-based CV parsing and matching pipeline.
""".strip()


@pytest.fixture
def sample_job_openings() -> list[dict[str, Any]]:
    """Standard job openings list fixture with realistic requirements and department taxonomy."""
    return [
        {
            "id": "job-101",
            "vacancy_id": 101,
            "title": "Senior Python Developer",
            "department": "Engineering",
            "department_id": 9,
            "domain": "Information Technology & Software",
            "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            "preferred_keywords": ["Redis", "Kubernetes", "AWS"],
            "min_experience_years": 4.0,
            "max_experience_years": 10.0,
            "required_qualifications": ["Bachelor", "B.Tech", "B.S. in Computer Science"],
            "description": "We are looking for an experienced Senior Python Developer to lead backend API and microservice development.",
        },
        {
            "id": "job-102",
            "vacancy_id": 102,
            "title": "Plant Electrical Maintenance Engineer",
            "department": "Operations",
            "department_id": 7,
            "domain": "Engineering",
            "required_skills": ["Switchgear", "Transformer", "High Voltage", "Preventive Maintenance"],
            "preferred_keywords": ["PLC", "SCADA"],
            "min_experience_years": 3.0,
            "max_experience_years": 8.0,
            "required_qualifications": ["Diploma or Degree in Electrical Engineering"],
            "description": "Seeking an Electrical Maintenance Engineer for substation, switchgear, and plant utility operations.",
        },
        {
            "id": "job-103",
            "vacancy_id": 103,
            "title": "Finance & Accounts Executive",
            "department": "Finance",
            "department_id": 8,
            "domain": "Finance & Accounting",
            "required_skills": ["Tally", "General Ledger", "Taxation", "Financial Statements"],
            "preferred_keywords": ["GST", "Auditing"],
            "min_experience_years": 2.0,
            "max_experience_years": 6.0,
            "required_qualifications": ["B.Com", "M.Com", "MBA Finance"],
            "description": "Looking for a Finance Executive to handle accounts payable, ledger reconciliation, and tax filings.",
        },
    ]
