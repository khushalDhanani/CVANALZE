from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.rule_config_manager import PolicyRegistry
from app.schemas.classification_types import NormalizedClassification
from app.services.domain_embedding_service import DomainEmbeddingService
from app.services.dynamic_taxonomy_service import (
    DynamicTaxonomyService,
)

router = APIRouter(prefix="/domain-knowledge", tags=["Domain Knowledge"])


class DomainEquivalentRequest(BaseModel):
    term: str = Field(..., description="Target domain term (e.g. 'Postgres' or 'Backend Developer')")
    category: str = Field(
        "skills",
        description="Domain category: 'skills', 'job_titles', 'departments', 'technologies', 'certifications', 'education_domains', 'industries', 'functional_areas'",
    )
    threshold: float | None = Field(None, ge=0.0, le=1.0, description="Minimum vector similarity threshold")
    limit: int | None = Field(None, ge=1, description="Maximum number of equivalent terms to return")


class DomainEquivalentResponse(BaseModel):
    term: str
    category: str
    equivalents: list[dict[str, Any]]


class AddDesignationRequest(BaseModel):
    designation_name: str = Field(..., min_length=1, description="Name of designation (e.g. 'Prompt Engineer')")
    family_name: str = Field(
        ...,
        min_length=1,
        description="Parent Job Family Name (e.g. 'Software Engineering & Development')",
    )
    synonyms: list[str] = Field(default_factory=list, description="List of aliases/synonyms")
    seniority_level: str = Field("Standard", description="Seniority level (e.g. Executive, Senior, Lead)")


class ResolveRoleRequest(BaseModel):
    role_or_summary: str = Field(..., min_length=1, description="Role title or candidate summary string")
    skills: list[str] = Field(default_factory=list, description="List of candidate skills")
    threshold: float | None = Field(None, ge=0.0, le=1.0, description="Similarity threshold for vector match")


@router.get("/categories", response_model=list[str])
def list_domain_categories() -> list[str]:
    """
    List all supported domain knowledge categories.
    """
    return sorted(DomainEmbeddingService.CATEGORIES)


@router.post("/equivalents", response_model=DomainEquivalentResponse)
def get_semantic_equivalents(
    request: DomainEquivalentRequest,
) -> DomainEquivalentResponse:
    """
    Resolve semantically equivalent domain terms for a given term and category.
    """
    cat = request.category.strip().lower()
    policy = PolicyRegistry.resolve_snapshot().similarity
    if cat not in DomainEmbeddingService.CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain category '{cat}'. Supported categories: {sorted(DomainEmbeddingService.CATEGORIES)}",
        )

    threshold = request.threshold if request.threshold is not None else policy.domain_default_threshold
    limit = request.limit if request.limit is not None else policy.domain_default_limit
    if threshold < policy.min_similarity_threshold or limit > policy.domain_max_limit:
        raise HTTPException(status_code=422, detail="Similarity threshold or result limit is outside the active policy.")
    equivalents = DomainEmbeddingService.find_semantic_equivalents(
        term=request.term,
        category=cat,
        threshold=threshold,
        limit=limit,
    )

    return DomainEquivalentResponse(
        term=request.term,
        category=cat,
        equivalents=equivalents,
    )


@router.post("/designations", response_model=dict[str, Any])
def add_new_designation(request: AddDesignationRequest) -> dict[str, Any]:
    """
    Dynamically add a new designation with synonyms to PostgreSQL taxonomy and pgvector.
    """
    success = DynamicTaxonomyService.add_designation(
        designation_name=request.designation_name,
        family_name=request.family_name,
        synonyms=request.synonyms,
        seniority_level=request.seniority_level,
    )
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to add designation '{request.designation_name}'. Ensure the parent family exists and embeddings are available.",
        )
    return {
        "status": "success",
        "message": f"Successfully added designation '{request.designation_name}' and generated vector embeddings.",
        "designation_name": request.designation_name,
        "family_name": request.family_name,
    }


@router.post("/resolve-role", response_model=NormalizedClassification)
def resolve_role_dynamically(request: ResolveRoleRequest) -> NormalizedClassification:
    """
    Dynamically resolve role, domain, and job family using vector similarity and MSSQL taxonomy.
    """
    policy = PolicyRegistry.resolve_snapshot().similarity
    threshold = request.threshold if request.threshold is not None else policy.role_resolution_threshold
    return DynamicTaxonomyService.resolve_candidate_role_and_domain(
        role_or_summary=request.role_or_summary,
        skills=request.skills,
        threshold=threshold,
    )
