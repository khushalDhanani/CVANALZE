from __future__ import annotations
from typing import Any

from fastapi import APIRouter, BackgroundTasks

from app.services.vector_migration_service import VectorDatabaseMigrationService

router = APIRouter(prefix="/vector-db", tags=["Vector Database"])


@router.get("/status", response_model=dict[str, Any])
def get_vector_db_status() -> dict[str, Any]:
    """
    Get PostgreSQL pgvector database connectivity health, table vector counts, and model configuration.
    """
    return VectorDatabaseMigrationService.get_migration_status()


@router.post("/sync", response_model=dict[str, Any])
def sync_vector_db(background_tasks: BackgroundTasks) -> dict[str, Any]:
    """
    Trigger background synchronization of candidate and vacancy embeddings into PostgreSQL pgvector database.
    """
    background_tasks.add_task(VectorDatabaseMigrationService.run_sync_safely)
    return {
        "message": "Vector database background synchronization started.",
        "status": "processing",
    }
