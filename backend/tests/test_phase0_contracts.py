from app.core.access_policy import COMPATIBILITY_ALIASES, ENDPOINT_POLICIES
from app.main import app
from app.schemas.analysis import EnrichedCandidateAnalysis
from app.schemas.contracts import (
    CanonicalError,
    ErrorCode,
    ErrorResponse,
    JobState,
    JobStateResponse,
    ProcessingOutcome,
    normalize_job_state,
)
from app.schemas.cv import CVProcessingResponse, CVUploadResponse


def _custom_application_routes() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        included_router = getattr(route, "original_router", None)
        if included_router is not None:
            prefix = route.include_context.prefix
            candidates = ((f"{prefix}{child.path}", child) for child in included_router.routes)
        else:
            candidates = ((getattr(route, "path", ""), route),)

        for path, candidate in candidates:
            if path not in ("/", "/health") and not path.startswith("/api/") and path != "/api/candidates":
                continue
            methods = getattr(candidate, "methods", None)
            if methods:
                routes.update((method, path) for method in methods if method not in ("HEAD", "OPTIONS"))
            else:
                routes.add(("WEBSOCKET", path))
    return routes


def test_every_application_route_has_an_access_policy():
    expected = {(policy.method, policy.path) for policy in ENDPOINT_POLICIES}

    assert _custom_application_routes() == expected


def test_openapi_path_and_method_snapshot_matches_access_policy():
    expected = {(policy.method, policy.path) for policy in ENDPOINT_POLICIES if policy.method != "WEBSOCKET"}
    actual = {(method.upper(), path) for path, path_item in app.openapi()["paths"].items() for method in path_item if method.lower() in {"get", "post", "put", "patch", "delete"}}

    assert actual == expected


def test_success_response_field_snapshots_are_stable():
    assert set(CVProcessingResponse.model_fields) == {
        "message",
        "cv_key",
        "status",
        "progress",
        "stage",
        "failed_step",
        "error_details",
        "job_id",
        "job_state",
        "execution_mode",
        "retry_count",
    }
    assert set(EnrichedCandidateAnalysis.model_fields) == {
        "status",
        "progress",
        "stage",
        "is_complete",
        "job_id",
        "job_state",
        "execution_mode",
        "retry_count",
        "full_name",
        "candidate_name",
        "primary_department",
        "recommended_department",
        "professional_domain",
        "strengths",
        "suitable_job_roles",
        "has_genuine_match",
        "active_vacancy_summary",
        "ai_career_summary",
        "best_match",
        "suitable_openings",
        "rejection_policy_note",
        "llm_skipped",
        "normalized_resume",
        "classification",
        "scoring_profile_code",
        "scoring_profile_version",
        "ai_career_suggestions",
        "unsuitable_openings",
        "config_version",
        "prompt_version",
    }
    assert set(CVUploadResponse.model_fields) == {
        "id",
        "scan_id",
        "parsed_at",
        "filename",
        "content_type",
        "characters",
        "page_count",
        "is_scanned",
        "ocr_applied",
        "text",
        "markdown",
        "structured_doc",
        "match_analysis",
        "result_file_path",
        "candidate_id",
        "cv_id",
        "cv_hash",
        "parser_version",
        "schema_version",
        "created_at",
        "updated_at",
        "status",
        "dynamic_profile",
        "quality_metrics",
        "resume_json",
        "normalized_resume",
        "full_name",
        "candidate_name",
        "email",
        "phone",
        "location",
        "job_title",
        "company_name",
        "name_confidence",
        "name_confidence_tier",
        "location_confidence_tier",
        "job_title_confidence_tier",
        "company_name_confidence_tier",
        "field_confidence",
        "field_confidence_tiers",
        "name_extraction_source",
        "job_id",
        "job_state",
        "execution_mode",
        "retry_count",
    }


def test_compatibility_aliases_reference_existing_routes():
    endpoints = {(policy.method, policy.path) for policy in ENDPOINT_POLICIES}

    for alias_group in COMPATIBILITY_ALIASES.values():
        assert len(alias_group) >= 2
        assert set(alias_group).issubset(endpoints)


def test_legacy_job_states_normalize_to_canonical_states():
    assert normalize_job_state("processing") == JobState.PROCESSING
    assert normalize_job_state("NEW_CV") == JobState.COMPLETED
    assert normalize_job_state("REPROCESSED") == JobState.COMPLETED
    assert normalize_job_state("CACHE_HIT") == JobState.COMPLETED
    assert normalize_job_state("FAILED") == JobState.FAILED
    assert normalize_job_state(None, progress=100) == JobState.COMPLETED


def test_job_state_contract_round_trips_to_legacy_polling_shape():
    canonical = JobStateResponse.from_legacy(
        {
            "id": "cv_jane_doe",
            "status": "COMPLETED",
            "original_status": "CACHE_HIT",
            "progress": 100,
            "stage": "complete",
            "message": "CV processing complete.",
        }
    )

    assert canonical.job_id == "cv_jane_doe"
    assert canonical.state == JobState.COMPLETED
    assert canonical.outcome == ProcessingOutcome.CACHE_HIT
    assert canonical.to_legacy_processing() == {
        "message": "CV processing complete.",
        "cv_key": "cv_jane_doe",
        "status": "COMPLETED",
        "progress": 100,
        "stage": "complete",
    }


def test_canonical_error_retains_legacy_detail_adapter():
    response = ErrorResponse(
        error=CanonicalError(
            code=ErrorCode.UNSUPPORTED_FILE,
            message="Unsupported CV file type.",
        )
    )

    assert response.to_legacy_detail() == {"detail": "Unsupported CV file type."}
