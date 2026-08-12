from __future__ import annotations
from typing import Any

from fastapi import APIRouter

from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["AI Recommendations"])


@router.get("/candidate/{candidate_id}", response_model=dict[str, Any])
def get_candidate_recommendations(candidate_id: str) -> dict[str, Any]:
    """
    Candidate AI Recommendations API.
    Returns best vacancies, related skills, missing qualifications, recommended certifications,
    career transition opportunities, and internal talent pool assignments.
    """
    return RecommendationService.get_candidate_recommendations(candidate_id)


@router.get("/vacancy/{vacancy_id}", response_model=dict[str, Any])
def get_vacancy_recommendations(vacancy_id: str) -> dict[str, Any]:
    """
    Vacancy AI Recommendations API.
    Returns top candidate matches, similar candidates, skill gap insights, and talent pool matches.
    """
    return RecommendationService.get_vacancy_recommendations(vacancy_id)


@router.get("/talent-pools", response_model=dict[str, Any])
def get_internal_talent_pools() -> dict[str, Any]:
    """
    Internal Talent Pools API.
    Returns list of dynamic candidate talent pools grouped by department, skill cluster, and experience tier.
    """
    return RecommendationService.get_internal_talent_pools()
