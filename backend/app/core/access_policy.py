from dataclasses import dataclass

from app.schemas.contracts import AccessTier


@dataclass(frozen=True)
class EndpointPolicy:
    method: str
    path: str
    access: AccessTier


ENDPOINT_POLICIES: tuple[EndpointPolicy, ...] = (
    EndpointPolicy("GET", "/", AccessTier.PUBLIC),
    EndpointPolicy("GET", "/health", AccessTier.PUBLIC),
    EndpointPolicy("GET", "/api/match/health", AccessTier.ADMINISTRATOR),
    EndpointPolicy("POST", "/api/match/analyze", AccessTier.RECRUITER),
    EndpointPolicy("POST", "/api/match/upload", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/match/status/{cv_key}", AccessTier.RECRUITER),
    EndpointPolicy("POST", "/api/match/reanalyze/{scan_id}", AccessTier.RECRUITER),
    EndpointPolicy("POST", "/api/match/hr-review", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/match/training-data", AccessTier.ADMINISTRATOR),
    EndpointPolicy("POST", "/api/cv/upload", AccessTier.RECRUITER),
    EndpointPolicy("POST", "/api/cv/match", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/cv/status/{cv_key}", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/jobs", AccessTier.RECRUITER),
    EndpointPolicy("POST", "/api/jobs/cache/invalidate", AccessTier.ADMINISTRATOR),
    EndpointPolicy("GET", "/api/jobs/{job_id}", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/master-data/job-profiles", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/master-data/departments", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/master-data/companies", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/master-data/skills", AccessTier.RECRUITER),
    EndpointPolicy("POST", "/api/master-data/warm", AccessTier.ADMINISTRATOR),
    EndpointPolicy("POST", "/api/batch/match-candidates", AccessTier.RECRUITER),
    EndpointPolicy("WEBSOCKET", "/api/batch/ws/progress", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/config/match", AccessTier.ADMINISTRATOR),
    EndpointPolicy("PUT", "/api/config/match", AccessTier.ADMINISTRATOR),
    EndpointPolicy("GET", "/api/config/active", AccessTier.ADMINISTRATOR),
    EndpointPolicy("POST", "/api/config/versions", AccessTier.ADMINISTRATOR),
    EndpointPolicy("POST", "/api/config/versions/{version_tag}/activate", AccessTier.ADMINISTRATOR),
    EndpointPolicy("POST", "/api/candidates/search", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/candidates", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/candidates/{candidate_id}", AccessTier.RECRUITER),
    EndpointPolicy("POST", "/api/candidates/{candidate_id}/reprocess", AccessTier.ADMINISTRATOR),
    EndpointPolicy("POST", "/api/v1/candidates/search", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/v1/candidates", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/v1/candidates/{candidate_id}", AccessTier.RECRUITER),
    EndpointPolicy("POST", "/api/v1/candidates/{candidate_id}/reprocess", AccessTier.ADMINISTRATOR),
    EndpointPolicy("GET", "/api/analytics/cache", AccessTier.ADMINISTRATOR),
    EndpointPolicy("GET", "/api/vector-db/status", AccessTier.ADMINISTRATOR),
    EndpointPolicy("POST", "/api/vector-db/sync", AccessTier.ADMINISTRATOR),
    EndpointPolicy("GET", "/api/domain-knowledge/categories", AccessTier.RECRUITER),
    EndpointPolicy("POST", "/api/domain-knowledge/equivalents", AccessTier.RECRUITER),
    EndpointPolicy("POST", "/api/domain-knowledge/designations", AccessTier.ADMINISTRATOR),
    EndpointPolicy("POST", "/api/domain-knowledge/resolve-role", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/talent-graph/candidate/{candidate_id}", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/talent-graph/vacancy/{vacancy_id}", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/talent-graph/skill/{skill_name}", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/talent-graph/analytics", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/recommendations/candidate/{candidate_id}", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/recommendations/vacancy/{vacancy_id}", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/recommendations/talent-pools", AccessTier.RECRUITER),
    EndpointPolicy("GET", "/api/performance/metrics", AccessTier.ADMINISTRATOR),
    EndpointPolicy("POST", "/api/performance/cache/invalidate", AccessTier.ADMINISTRATOR),
)


COMPATIBILITY_ALIASES: dict[str, tuple[tuple[str, str], ...]] = {
    "cv_upload": (
        ("POST", "/api/cv/upload"),
        ("POST", "/api/match/upload"),
    ),
    "cv_status": (
        ("GET", "/api/cv/status/{cv_key}"),
        ("GET", "/api/match/status/{cv_key}"),
    ),
    "cv_text_match": (
        ("POST", "/api/cv/match"),
        ("POST", "/api/match/analyze"),
    ),
    "candidate_routes": (
        ("POST", "/api/candidates/search"),
        ("POST", "/api/v1/candidates/search"),
        ("GET", "/api/candidates"),
        ("GET", "/api/v1/candidates"),
        ("GET", "/api/candidates/{candidate_id}"),
        ("GET", "/api/v1/candidates/{candidate_id}"),
        ("POST", "/api/candidates/{candidate_id}/reprocess"),
        ("POST", "/api/v1/candidates/{candidate_id}/reprocess"),
    ),
}


def get_access_tier(method: str, path: str) -> AccessTier | None:
    normalized_method = method.strip().upper()
    for policy in ENDPOINT_POLICIES:
        if policy.method == normalized_method and policy.path == path:
            return policy.access
    return None


def resolve_access_tier(method: str, request_path: str) -> AccessTier | None:
    """Resolve a concrete request path against the characterized route templates."""
    normalized_method = method.strip().upper()
    request_segments = _path_segments(request_path)
    for policy in ENDPOINT_POLICIES:
        if policy.method != normalized_method:
            continue
        policy_segments = _path_segments(policy.path)
        if len(policy_segments) != len(request_segments):
            continue
        segments_match = all((expected.startswith("{") and expected.endswith("}")) or expected == actual for expected, actual in zip(policy_segments, request_segments))
        if segments_match:
            return policy.access
    return None


def _path_segments(path: str) -> tuple[str, ...]:
    return tuple(segment for segment in path.strip().split("/") if segment)
