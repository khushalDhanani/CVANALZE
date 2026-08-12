"""Reprocess matching-quality regression fixtures from their retained raw documents."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.repositories.result import ResultRepository
from app.services.cv_service import process_cv_file


FIXTURE_PATH = BACKEND_DIR / "tests" / "fixtures" / "matching_quality" / "regression_cvs.json"
UPLOADS_DIR = BACKEND_DIR / "uploads"


def _source_path(cv_key: str, existing: dict[str, Any]) -> Path:
    storage_filename = str(existing.get("storage_filename") or "").strip()
    if storage_filename and (UPLOADS_DIR / storage_filename).is_file():
        return UPLOADS_DIR / storage_filename
    candidates = sorted(UPLOADS_DIR.glob(f"{cv_key}_*"))
    if not candidates:
        raise FileNotFoundError(f"No retained raw document found for fixture '{cv_key}'.")
    return candidates[0]


async def reprocess() -> list[dict[str, Any]]:
    fixtures = json.loads(FIXTURE_PATH.read_text())
    summaries: list[dict[str, Any]] = []
    for fixture in fixtures:
        cv_key = fixture["fixture_id"]
        existing = ResultRepository.resolve_result(cv_key)
        if not existing:
            raise RuntimeError(f"No existing candidate result found for fixture '{cv_key}'.")
        source_path = _source_path(cv_key, existing)
        result = await process_cv_file(
            filename=str(existing.get("filename") or f"{cv_key}.pdf"),
            content=source_path.read_bytes(),
            content_type="application/pdf",
            candidate_id=existing.get("candidate_id"),
            source_candidate_id=existing.get("source_candidate_id"),
            cv_id=existing.get("cv_id"),
            force_reprocess=True,
            storage_filename=source_path.name,
        )
        match_analysis = result.get("match_analysis") or {}
        best_match = match_analysis.get("best_match") or {}
        summaries.append(
            {
                "fixture_id": cv_key,
                "status": result.get("status"),
                "match_status": match_analysis.get("match_status") or result.get("match_status"),
                "name": result.get("full_name") or result.get("candidate_name"),
                "experience_years": result.get("experience_years"),
                "professional_domain": match_analysis.get("professional_domain") or result.get("professional_domain"),
                "best_vacancy_id": best_match.get("vacancy_id"),
                "best_vacancy": best_match.get("job_title"),
                "best_score": best_match.get("vacancy_fit_score"),
            }
        )
    return summaries


if __name__ == "__main__":
    print(json.dumps(asyncio.run(reprocess()), indent=2))
