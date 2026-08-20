from __future__ import annotations

from pydantic import BaseModel, Field


class AnalysisVersions(BaseModel):
    """
    Complete analysis lineage and component version provenance.
    Guarantees every candidate score & decision is traceable to exact system versions.
    """

    app_version: str = Field(default="1.1.0", description="Application semantic version")
    git_sha: str = Field(default="head", description="Git commit hash of active build")
    parser_version: str = Field(default="v2.1-docling", description="Document parser & layout engine version")
    normalization_version: str = Field(default="v1.4-taxonomy", description="Text normalization & alias engine version")
    taxonomy_version: str = Field(default="v3.0-enterprise", description="Taxonomy classification & DB schema version")
    policy_snapshot_id: str = Field(default="snap_1.1.0_1b5d9c5a", description="Active PolicySnapshot identifier")
    embedding_model_id: str = Field(default="nomic-embed-text", description="Dense vector embedding model identifier")
    generation_model_id: str = Field(default="gemma2:9b-instruct-q4_K_M", description="Active LLM generation model identifier")
    prompt_version: str = Field(default="4.0", description="Authoritative prompt template version")
    schema_version: str = Field(default="v1.0", description="API contract & vector schema version")
    policy_source: str = Field(default="DATABASE", description="Policy provenance source (e.g. DATABASE, bundled_static, EMERGENCY_BUNDLED)")
    degraded_mode: bool = Field(default=False, description="Whether analysis ran under degraded mode or policy fallback")


class ChunkingProfile(BaseModel):
    """
    Token-aware, section-aware document chunking strategy profile.
    Replaces fixed character limits with section boundaries and token budgets.
    """

    chunk_strategy_version: str = Field(default="v1.0-section-aware", description="Chunking algorithm version")
    token_budget: int = Field(default=1200, description="Max token budget per chunk")
    overlap_tokens: int = Field(default=100, description="Token overlap between consecutive chunks")
    preserve_sections: bool = Field(default=True, description="Whether section boundaries are respected")
    normalization_mode: str = Field(default="l2_normalized", description="Vector normalization mode")
