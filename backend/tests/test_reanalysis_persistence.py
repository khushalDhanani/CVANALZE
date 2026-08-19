from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.result import ResultRepository
from app.schemas.contracts import ErrorCode
from app.services.match_service import MatchService
from app.services.ollama_transport import (
    OllamaError,
    OllamaInvalidResponseError,
    OllamaModelUnavailableError,
    OllamaTimeoutError,
    OllamaTransport,
    OllamaTransportResult,
    OllamaUnavailableError,
)
from app.services.processing_queue import _process_source, _safe_processing_error


client = TestClient(app)


class _ReanalyzedResult:
    def __init__(self, opening=None):
        self.opening = opening or {"job_id": "vacancy-1", "llm_reason": "new reasoning"}

    def model_dump(self):
        return {
            "best_match": self.opening,
            "suitable_openings": [self.opening],
            "unsuitable_openings": [],
        }


def test_reanalysis_updates_the_canonical_candidate_result(monkeypatch):
    semantic_reason = "Candidate has relevant organic chemistry laboratory experience."
    canonical_filename = "cv_123.json"
    stored_result = {
        "id": "cv_123",
        "scan_id": "cv_123",
        "filename": "candidate.pdf",
        "parsed_at": "2026-08-13T00:00:00Z",
        "markdown": "Candidate resume text",
        "resume_json": {},
        "status": "COMPLETED",
        "match_analysis": {
            "best_match": {"job_id": "vacancy-1", "llm_reason": "old"},
            "suitable_openings": [],
            "unsuitable_openings": [],
        },
    }
    saved_filenames = []

    def resolve_result(candidate_key):
        if candidate_key.removesuffix(".json") == "cv_123":
            return stored_result
        return None

    def read_result(reference):
        if str(reference).removesuffix(".json") == "cv_123":
            return stored_result
        raise FileNotFoundError(reference)

    def atomic_save_result(filename, data):
        saved_filenames.append(filename)
        return filename

    def generate(_cls, *, operation, payload, parser):
        assert operation == "optimized_match"
        deterministic_output = {
            "matches": [
                {
                    "vacancy_id": "123",
                    "semantic_reason": semantic_reason,
                    "inferred_skills": ["titration", "distillation"],
                }
            ]
        }
        return OllamaTransportResult(
            value=parser(deterministic_output),
            response_data=deterministic_output,
            duration_ms=1.0,
            attempts=1,
        )

    async def analyze_single_cv(*args, **kwargs):
        assert kwargs["force_reanalysis"] is True
        generated = OllamaTransport.generate(
            operation="optimized_match",
            payload={"model": "test", "prompt": "candidate"},
            parser=lambda response: response,
        ).value
        match = generated["matches"][0]
        return _ReanalyzedResult(
            {
                "job_id": match["vacancy_id"],
                "vacancy_id": match["vacancy_id"],
                "llm_reason": match["semantic_reason"],
                "inferred_skills": match["inferred_skills"],
            }
        )

    monkeypatch.setattr(ResultRepository, "resolve_result", resolve_result)
    monkeypatch.setattr(ResultRepository, "read_result", read_result)
    monkeypatch.setattr(ResultRepository, "atomic_save_result", atomic_save_result)
    monkeypatch.setattr(MatchService, "analyze_single_cv", analyze_single_cv)
    monkeypatch.setattr(OllamaTransport, "generate", classmethod(generate))

    reanalysis_response = client.post("/api/match/reanalyze/cv_123")
    assert reanalysis_response.status_code == 200
    assert reanalysis_response.json()["match_analysis"]["best_match"]["llm_reason"] == semantic_reason
    assert reanalysis_response.json()["match_analysis"]["best_match"]["inferred_skills"] == ["titration", "distillation"]
    assert reanalysis_response.json()["analysis_run_id"].startswith("analysis_")
    assert reanalysis_response.json()["analysis_version"] == reanalysis_response.json()["analysis_run_id"]

    candidate_response = client.get("/api/v1/candidates/cv_123")
    assert candidate_response.status_code == 200
    assert candidate_response.json()["match_analysis"]["best_match"]["llm_reason"] == semantic_reason
    assert candidate_response.json()["enriched_match_analysis"]["best_match"]["llm_reason"] == semantic_reason
    assert candidate_response.json()["analysis_run_id"] == reanalysis_response.json()["analysis_run_id"]
    assert candidate_response.json()["analysis_version"] == reanalysis_response.json()["analysis_version"]
    assert ResultRepository.resolve_result("cv_123")["match_analysis"]["best_match"]["llm_reason"] == semantic_reason
    assert saved_filenames == [canonical_filename]
    assert not any(filename.endswith("_enriched.json") for filename in saved_filenames)


def test_historical_result_artifacts_are_not_canonical_candidates():
    assert ResultRepository._is_historical_result_reference("cv_123_enriched.json") is True
    assert ResultRepository._is_historical_result_reference("redis://cv_result:cv_123_latest.json") is True
    assert ResultRepository._is_historical_result_reference("cv_123.json") is False


@pytest.mark.parametrize(
    ("service_error", "expected_code"),
    [
        (OllamaTimeoutError("timed out", operation="optimized_match"), ErrorCode.LLM_TIMEOUT),
        (OllamaUnavailableError("offline", operation="optimized_match"), ErrorCode.LLM_UNAVAILABLE),
        (OllamaInvalidResponseError("invalid", operation="optimized_match"), ErrorCode.ANALYSIS_INVALID),
    ],
)
def test_background_analysis_failures_do_not_become_no_match(service_error, expected_code):
    error = _safe_processing_error(service_error, retryable=True, correlation_id="analysis_test")

    assert error.code == expected_code
    assert error.code.value != "NO_MATCH"
    assert error.correlation_id == "analysis_test"


@pytest.mark.asyncio
async def test_rq_attempt_identity_propagates_as_analysis_run_id(monkeypatch):
    captured = {}

    async def process_cv_file(**kwargs):
        captured.update(kwargs)
        return {"analysis_run_id": kwargs["analysis_run_id"]}

    monkeypatch.setattr("app.services.cv_service.process_cv_file", process_cv_file)
    record = SimpleNamespace(
        rq_job_id="cv-job-1",
        job_id="cv-job",
        cv_key="cv_test",
        candidate_id="candidate-1",
        source_candidate_id=1,
        cv_id="cv-1",
        force_reprocess=False,
    )

    result = await _process_source(
        record=record,
        filename="candidate.pdf",
        content=b"resume",
        content_type="application/pdf",
        storage_filename="stored.pdf",
    )

    assert result["analysis_run_id"] == "cv-job-1"
    assert captured["analysis_run_id"] == "cv-job-1"


@pytest.mark.parametrize(
    ("service_error", "expected_status", "expected_detail"),
    [
        (OllamaTimeoutError("timed out", operation="optimized_match"), 504, "LLM generation timed out"),
        (OllamaModelUnavailableError("missing-model", operation="optimized_match"), 503, "missing-model"),
        (OllamaInvalidResponseError("invalid JSON", operation="optimized_match"), 422, "invalid structured response"),
        (OllamaError("service unavailable", operation="optimized_match"), 503, "LLM service is unavailable"),
    ],
)
def test_reanalysis_preserves_actionable_llm_failure_categories(monkeypatch, service_error, expected_status, expected_detail):
    monkeypatch.setattr(ResultRepository, "resolve_result", lambda _: {"id": "cv_123", "scan_id": "cv_123"})

    async def fail_reanalysis(_):
        raise service_error

    monkeypatch.setattr(MatchService, "analyze_from_result_file", fail_reanalysis)

    response = client.post("/api/match/reanalyze/cv_123")
    assert response.status_code == expected_status
    assert expected_detail in response.json()["detail"]
