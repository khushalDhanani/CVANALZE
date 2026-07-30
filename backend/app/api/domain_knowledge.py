from typing import Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from app.services.domain_embedding_service import DomainEmbeddingService

router = APIRouter(prefix="/domain-knowledge", tags=["Domain Knowledge"])


class DomainEquivalentRequest(BaseModel):
    term: str = Field(..., description="Target domain term (e.g. 'Postgres' or 'Backend Developer')")
    category: str = Field(
        "skills",
        description="Domain category: 'skills', 'job_titles', 'departments', 'technologies', 'certifications', 'education_domains', 'industries', 'functional_areas'",
    )
    threshold: float = Field(0.82, ge=0.0, le=1.0, description="Minimum vector similarity threshold")
    limit: int = Field(5, ge=1, le=50, description="Maximum number of equivalent terms to return")


class DomainEquivalentResponse(BaseModel):
    term: str
    category: str
    equivalents: list[dict[str, Any]]


@router.get("/categories", response_model=list[str])
def list_domain_categories() -> list[str]:
    """
    List all supported domain knowledge categories.
    """
    return sorted(list(DomainEmbeddingService.CATEGORIES))


@router.post("/equivalents", response_model=DomainEquivalentResponse)
def get_semantic_equivalents(request: DomainEquivalentRequest) -> DomainEquivalentResponse:
    """
    Resolve semantically equivalent domain terms for a given term and category.
    """
    cat = request.category.strip().lower()
    if cat not in DomainEmbeddingService.CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain category '{cat}'. Supported categories: {sorted(list(DomainEmbeddingService.CATEGORIES))}",
        )

    equivalents = DomainEmbeddingService.find_semantic_equivalents(
        term=request.term,
        category=cat,
        threshold=request.threshold,
        limit=request.limit,
    )

    return DomainEquivalentResponse(
        term=request.term,
        category=cat,
        equivalents=equivalents,
    )
