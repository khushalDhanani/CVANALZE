from uuid import uuid4


def build_rq_worker_name(role: str) -> str:
    """Return a stable-role, unique process identity that cannot collide with stale RQ registrations."""
    normalized_role = "-".join(role.strip().split())
    if not normalized_role:
        raise ValueError("RQ worker role must not be empty.")
    return f"{normalized_role}-{uuid4().hex}"
