from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel, Field


class AnalysisFingerprint(BaseModel):
    """
    Unified Analysis Fingerprint.
    Builds single deterministic cache identity from all 11 version & revision inputs
    that can alter candidate conclusions.
    """

    source_document_hash: str = Field(..., description="SHA-256 content hash of raw candidate document")
    candidate_revision: str = Field(default="rev_1", description="Candidate profile revision watermark")
    vacancy_revision: str = Field(default="vac_rev_1", description="Target vacancy definition revision watermark")
    parser_version: str = Field(default="v2.1-docling", description="Document parser version")
    normalization_version: str = Field(default="v1.4-taxonomy", description="Text normalization engine version")
    taxonomy_version: str = Field(default="v3.0-enterprise", description="Taxonomy classification engine version")
    policy_snapshot_id: str = Field(default="snap_1.1.0_1b5d9c5a", description="Active PolicySnapshot identifier")
    embedding_model_id: str = Field(default="nomic-embed-text", description="Dense vector embedding model identifier")
    generation_model_id: str = Field(default="gemma2:9b-instruct-q4_K_M", description="Active LLM generation model identifier")
    prompt_version: str = Field(default="4.0", description="Authoritative prompt template version")
    schema_version: str = Field(default="v1.0", description="API contract & vector schema version")

    def compute_fingerprint_digest(self) -> str:
        """Calculate deterministic SHA-256 hex digest across all 11 component fields."""
        data = self.model_dump()
        sorted_items = sorted(data.items())
        raw_str = "|".join(f"{k}={v}" for k, v in sorted_items)
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    @classmethod
    def create(
        cls,
        source_document_hash: str,
        candidate_revision: str = "rev_1",
        vacancy_revision: str = "vac_rev_1",
        policy_snapshot_id: str | None = None,
        versions_obj: Any = None,
    ) -> "AnalysisFingerprint":
        """Factory method constructing AnalysisFingerprint from version provenance."""
        if versions_obj is not None:
            return cls(
                source_document_hash=source_document_hash,
                candidate_revision=candidate_revision,
                vacancy_revision=vacancy_revision,
                parser_version=getattr(versions_obj, "parser_version", "v2.1-docling"),
                normalization_version=getattr(versions_obj, "normalization_version", "v1.4-taxonomy"),
                taxonomy_version=getattr(versions_obj, "taxonomy_version", "v3.0-enterprise"),
                policy_snapshot_id=policy_snapshot_id or getattr(versions_obj, "policy_snapshot_id", "snap_1.1.0_1b5d9c5a"),
                embedding_model_id=getattr(versions_obj, "embedding_model_id", "nomic-embed-text"),
                generation_model_id=getattr(versions_obj, "generation_model_id", "gemma2:9b-instruct-q4_K_M"),
                prompt_version=getattr(versions_obj, "prompt_version", "4.0"),
                schema_version=getattr(versions_obj, "schema_version", "v1.0"),
            )
        return cls(
            source_document_hash=source_document_hash,
            candidate_revision=candidate_revision,
            vacancy_revision=vacancy_revision,
            policy_snapshot_id=policy_snapshot_id or "snap_1.1.0_1b5d9c5a",
        )
