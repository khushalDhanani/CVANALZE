from __future__ import annotations

from app.core.model_registry import ModelRegistry
from app.schemas.analysis_versions import AnalysisVersions, ChunkingProfile


def test_model_registry_metadata_and_defaults() -> None:
    """Workstream 5.1: ModelRegistry tracks metadata, version digests, and vector schema versions."""
    llm_meta = ModelRegistry.get_active_llm()
    embed_meta = ModelRegistry.get_active_embedding()

    assert llm_meta.name is not None
    assert embed_meta.name is not None
    assert embed_meta.dimension == 768
    assert embed_meta.normalization_mode == "l2_normalized"
    assert embed_meta.vector_schema_version == "v1.0"


def test_verify_vector_schema() -> None:
    """Workstream 5.1: ModelRegistry verifies embedding model ID, dimension, and vector schema version."""
    embed_meta = ModelRegistry.get_active_embedding()

    assert ModelRegistry.verify_vector_schema(embed_meta.name, dimension=768, schema_version="v1.0") is True
    # Mismatched dimension fails verification
    assert ModelRegistry.verify_vector_schema(embed_meta.name, dimension=512, schema_version="v1.0") is False
    # Mismatched schema version fails verification
    assert ModelRegistry.verify_vector_schema(embed_meta.name, dimension=768, schema_version="v9.9") is False


def test_analysis_versions_provenance_resolution() -> None:
    """Workstream 5.1: AnalysisVersions captures full 10-field component lineage."""
    versions = ModelRegistry.resolve_analysis_versions(policy_snapshot_id="snap_test_123")

    assert isinstance(versions, AnalysisVersions)
    assert versions.app_version == "1.1.0"
    assert versions.git_sha == "head"
    assert versions.parser_version == "v2.1-docling"
    assert versions.normalization_version == "v1.4-taxonomy"
    assert versions.taxonomy_version == "v3.0-enterprise"
    assert versions.policy_snapshot_id == "snap_test_123"
    assert versions.embedding_model_id == "nomic-embed-text"
    assert versions.generation_model_id is not None
    assert versions.prompt_version == "4.0"
    assert versions.schema_version == "v1.0"


def test_chunking_profile_token_and_section_aware() -> None:
    """Workstream 5.1: ChunkingProfile defines token-aware and section-aware chunking strategy."""
    profile = ChunkingProfile()

    assert profile.chunk_strategy_version == "v1.0-section-aware"
    assert profile.token_budget == 1200
    assert profile.overlap_tokens == 100
    assert profile.preserve_sections is True
    assert profile.normalization_mode == "l2_normalized"
