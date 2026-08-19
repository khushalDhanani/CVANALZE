from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.core.config import settings
from app.prompts.optimized_match import build_optimized_match_prompt
from app.repositories.processing_job import ProcessingJobRepository
from app.schemas.contracts import JobState, ProcessingExecutionMode, ProcessingJobRecord
from app.services.cv_service import process_cv_file


def _dummy_job(job_id: int) -> dict:
    return {
        "vacancy_id": job_id,
        "title": f"Software Engineer {job_id}",
        "department": "Engineering",
        "required_skills": ["Python", "FastAPI", "Docker", "SQL"],
        "required_skills_are_mandatory": True,
        "preferred_keywords": ["Redis", "PostgreSQL", "CI/CD"],
        "min_experience_years": 3,
        "max_experience_years": 6,
        "max_ctc": 30,
        "education": ["Bachelor's Degree in Computer Science"],
        "certifications": ["AWS Certified"],
        "technologies": ["Git", "Linux", "Kubernetes"],
        "responsibilities": ["Design APIs", "Maintain microservices", "Write unit tests"],
        "description": "Responsible for delivering high-performance backend microservices and maintaining data pipelines.",
    }


def test_ollama_settings_aligned():
    assert settings.OLLAMA_REQUEST_TIMEOUT == 180.0
    assert settings.LLM_TOP_N == 6
    assert settings.OLLAMA_GENERATE_TIMEOUT_SECONDS == 360.0
    assert settings.OLLAMA_OPTIMIZED_NUM_CTX == 16384


def test_build_optimized_match_prompt_budget_within_context_limits():
    cv_text = """
    Jane Recruiter
    Senior Backend Architect
    Experience: 8 years building Python, FastAPI, distributed systems, Docker, Redis, Kubernetes.
    Education: B.S. Computer Science.
    """
    vacancies = [_dummy_job(i) for i in range(1, 7)]

    with patch("app.services.prompt_service.PromptService.get_prompt") as mock_get_prompt:
        mock_get_prompt.return_value = "Optimized match prompt"
        prompt, token_est, char_count = build_optimized_match_prompt(cv_text, vacancies)

    # 6 vacancies with bounded descriptions must be well below 8192 context window
    assert token_est < 4000
    assert char_count < 20000


@pytest.mark.asyncio
async def test_process_cv_file_updates_processing_job_progress(monkeypatch):
    job_id = "cvjob_test_progress_tracking_123456"
    record = ProcessingJobRecord(
        job_id=job_id,
        cv_key="cv_test_progress_candidate",
        content_hash="hash_12345",
        filename="resume.pdf",
        storage_filename="cv_resume.pdf",
        content_type="application/pdf",
        candidate_id=None,
        source_candidate_id=None,
        cv_id=None,
        parser_version="1.0.0",
        schema_version="2.0.0",
        state=JobState.PROCESSING,
        progress=15,
        stage="source_validation",
        message="15% - Started",
        execution_mode=ProcessingExecutionMode.RQ,
        rq_job_id="rq_test_123",
        attempt=1,
        max_attempts=3,
        enqueue_count=1,
        force_reprocess=False,
        created_at=datetime.now(timezone.utc),
    )

    transitions = []

    def mock_transition(jid, state, *, progress=None, stage=None, message=None, **kwargs):
        transitions.append({"job_id": jid, "state": state, "progress": progress, "stage": stage})
        return record.model_copy(update={"progress": progress, "stage": stage})

    monkeypatch.setattr(ProcessingJobRepository, "transition", mock_transition)
    monkeypatch.setattr(ProcessingJobRepository, "get", lambda jid: record)

    # Mock extraction and matching stages to observe interim transitions
    with (
        patch("app.services.document_parser.MarkdownGenerator.generate_with_timeout") as mock_gen,
        patch("app.services.document_parser.ResumeJsonExtractor.extract") as mock_ext,
        patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=[0.1] * 768),
        patch("app.services.embedding_service.save_candidate_embedding"),
        patch("app.services.match_service.MatchService.analyze_single_cv") as mock_match,
        patch("app.repositories.result.ResultRepository.atomic_save_result", return_value="/tmp/test.json"),
        patch("app.services.upload_service.UploadService.cleanup_after_processing"),
    ):
        mock_result = MagicMock()
        mock_result.markdown = "# Resume\nCandidate details"
        mock_result.page_count = 1
        mock_result.pdf_type = "TEXT"
        mock_result.parser_used = "docling"
        mock_result.ocr_applied = False
        mock_result.is_scanned = False
        mock_result.to_dict.return_value = {}
        mock_gen.return_value = mock_result

        mock_ext.return_value = {
            "normalized": {
                "candidate_name": "Test Candidate",
                "skills": ["Python"],
                "experience": {"authoritative_years": 4.0, "total_months": 48},
                "education": {"degrees": []},
            },
            "contact_info": {"name": "Test Candidate"},
            "work_experience": [],
        }

        mock_match_analysis = MagicMock()
        mock_match_analysis.model_dump.return_value = {"matched_vacancies": []}
        mock_match.return_value = mock_match_analysis

        await process_cv_file(
            filename="resume.pdf",
            content=b"%PDF-1.4 mock",
            job_id=job_id,
        )

    # Verify stage progression occurred through 15, 30, 45, 60, 75, 90
    progress_values = [t["progress"] for t in transitions if t.get("job_id") == job_id]
    assert 15 in progress_values
    assert 30 in progress_values
    assert 45 in progress_values
    assert 60 in progress_values
    assert 75 in progress_values
    assert 90 in progress_values
