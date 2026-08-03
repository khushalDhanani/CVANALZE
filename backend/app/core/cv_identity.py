import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class CVIdentityCollisionError(ValueError):
    """Raised when a canonical key is already owned by a different CV identity."""


@dataclass(frozen=True)
class CVIdentity:
    canonical_key: str
    legacy_key: str
    candidate_id: str | None
    cv_id: str | None
    strategy: str

    @property
    def uses_supplied_ids(self) -> bool:
        return self.candidate_id is not None or self.cv_id is not None

    def to_metadata(self) -> dict[str, str | None]:
        return {
            "canonical_key": self.canonical_key,
            "legacy_key": self.legacy_key,
            "candidate_id": self.candidate_id,
            "cv_id": self.cv_id,
            "strategy": self.strategy,
        }


def _clean_supplied_id(value: str | int | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _safe_component(value: str) -> str:
    safe_value = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("._-")
    if not safe_value:
        safe_value = "id"
    if safe_value != value or len(safe_value) > 64:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
        safe_value = f"{safe_value[:48].rstrip('._-') or 'id'}_{digest}"
    return safe_value


def get_legacy_cv_key(filename: str) -> str:
    basename = PurePosixPath(filename.replace("\\", "/")).name
    raw_stem = Path(basename).stem
    safe_stem = re.sub(r"[^A-Za-z0-9_-]", "_", raw_stem).strip("._-") or "document"
    if safe_stem.lower().startswith("cv_"):
        safe_stem = safe_stem[3:]
    return f"cv_{safe_stem or 'document'}"


def resolve_cv_identity(
    filename: str,
    candidate_id: str | int | None = None,
    cv_id: str | int | None = None,
) -> CVIdentity:
    clean_candidate_id = _clean_supplied_id(candidate_id)
    clean_cv_id = _clean_supplied_id(cv_id)
    legacy_key = get_legacy_cv_key(filename)

    if clean_candidate_id and clean_cv_id:
        canonical_key = f"cv_candidate_{_safe_component(clean_candidate_id)}_document_{_safe_component(clean_cv_id)}"
        strategy = "candidate_and_cv_ids"
    elif clean_cv_id:
        canonical_key = f"cv_document_{_safe_component(clean_cv_id)}"
        strategy = "cv_id"
    elif clean_candidate_id:
        canonical_key = f"cv_candidate_{_safe_component(clean_candidate_id)}"
        strategy = "candidate_id"
    else:
        canonical_key = legacy_key
        strategy = "legacy_filename"

    return CVIdentity(
        canonical_key=canonical_key,
        legacy_key=legacy_key,
        candidate_id=clean_candidate_id,
        cv_id=clean_cv_id,
        strategy=strategy,
    )
