from app.core.access_policy import COMPATIBILITY_ALIASES, ENDPOINT_POLICIES
from app.main import app
from app.schemas.contracts import (
    CanonicalError,
    ErrorCode,
    ErrorResponse,
    JobState,
    JobStateResponse,
    ProcessingOutcome,
    normalize_job_state,
)


def _custom_application_routes() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        if path not in ("/", "/health") and not path.startswith("/api/") and path != "/api/candidates":
            continue
        methods = getattr(route, "methods", None)
        if methods:
            routes.update((method, path) for method in methods if method not in ("HEAD", "OPTIONS"))
        else:
            routes.add(("WEBSOCKET", path))
    return routes


def test_every_application_route_has_an_access_policy():
    expected = {(policy.method, policy.path) for policy in ENDPOINT_POLICIES}

    assert _custom_application_routes() == expected


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
