from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.config import settings

logger = logging.getLogger("cv_analyzer")


class ModelType(str, Enum):
    LLM = "LLM"
    EMBEDDING = "EMBEDDING"


class ModelHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNREACHABLE = "UNREACHABLE"
    UNKNOWN = "UNKNOWN"


@dataclass
class ModelMetadata:
    name: str
    model_type: ModelType
    dimension: int | None = None
    context_window: int = 4096
    timeout_seconds: float = 30.0
    is_active: bool = True
    health_status: ModelHealthStatus = ModelHealthStatus.UNKNOWN
    last_probe_at: float | None = None
    last_latency_ms: float | None = None
    probe_fail_count: int = 0
    version_digest: str = "v1.0"
    normalization_mode: str = "l2_normalized"
    supported_policy_versions: list[str] = field(default_factory=lambda: ["v1.0.0", "v1.1.0", "v2.0.0"])
    vector_schema_version: str = "v1.0"


class ModelRegistry:
    """
    Centralized Model & Embedding Registry.
    Tracks active model metadata, vector dimensions, context window limits,
    health probe states, and graceful runtime fallbacks.
    """

    _lock = threading.RLock()
    _models: dict[str, ModelMetadata] = {}

    @staticmethod
    def supports_thinking(model_name: str) -> bool:
        """Return configured generation capability for a normalized model family."""
        model_family = model_name.strip().lower().split(":", 1)[0].rsplit("/", 1)[-1]
        configured_families = {
            family.strip().lower()
            for family in settings.OLLAMA_THINKING_MODEL_FAMILIES
            if family.strip()
        }
        return model_family in configured_families

    @classmethod
    def initialize_defaults(cls) -> None:
        """Register default models configured in application settings."""
        with cls._lock:
            if not cls._models:
                # Active LLM Model
                cls._models[settings.OLLAMA_MODEL] = ModelMetadata(
                    name=settings.OLLAMA_MODEL,
                    model_type=ModelType.LLM,
                    context_window=settings.LLM_CONTEXT_CV_TOKEN_BUDGET or 4096,
                    timeout_seconds=getattr(settings, "OLLAMA_REQUEST_TIMEOUT", 900.0),
                    is_active=True,
                    version_digest="gemma2-9b-q4",
                )
                # Active Embedding Model
                cls._models[settings.EMBEDDING_MODEL] = ModelMetadata(
                    name=settings.EMBEDDING_MODEL,
                    model_type=ModelType.EMBEDDING,
                    dimension=getattr(settings, "OLLAMA_EMBEDDING_EXPECTED_DIMENSION", 768),
                    context_window=2048,
                    timeout_seconds=getattr(settings, "OLLAMA_EMBED_TIMEOUT_SECONDS", 60.0),
                    is_active=True,
                    version_digest="nomic-embed-v1.5",
                )

    @classmethod
    def verify_vector_schema(
        cls,
        model_id: str | None = None,
        dimension: int | None = None,
        schema_version: str | None = None,
    ) -> bool:
        """Verify model ID, dimension, and schema version before pgvector operations."""
        with cls._lock:
            cls.initialize_defaults()
            target_model = model_id or settings.EMBEDDING_MODEL
            meta = cls._models.get(target_model)
            if meta is None:
                return True  # Fallback permissive for unregistered test models
            if dimension is not None and meta.dimension is not None and dimension != meta.dimension:
                logger.warning(f"[VECTOR_SCHEMA] Dimension mismatch: expected {meta.dimension}, got {dimension}")
                return False
            if schema_version is not None and meta.vector_schema_version != schema_version:
                logger.warning(f"[VECTOR_SCHEMA] Schema version mismatch: expected {meta.vector_schema_version}, got {schema_version}")
                return False
            return True

    @classmethod
    def resolve_analysis_versions(cls, policy_snapshot_id: str | None = None) -> Any:
        """Construct immutable AnalysisVersions provenance object for analysis outputs."""
        from app.schemas.analysis_versions import AnalysisVersions
        from app.core.rule_config_manager import PolicyRegistry

        snapshot = PolicyRegistry.resolve_snapshot()
        pid = policy_snapshot_id or snapshot.metadata.policy_snapshot_id

        return AnalysisVersions(
            app_version="1.1.0",
            git_sha="head",
            parser_version="v2.1-docling",
            normalization_version="v1.4-taxonomy",
            taxonomy_version="v3.0-enterprise",
            policy_snapshot_id=pid,
            embedding_model_id=settings.EMBEDDING_MODEL,
            generation_model_id=settings.OLLAMA_MODEL,
            prompt_version=settings.OPTIMIZED_PROMPT_VERSION,
            schema_version="v1.0",
        )

    @classmethod
    def register_model(cls, meta: ModelMetadata) -> None:
        with cls._lock:
            cls._models[meta.name] = meta

    @classmethod
    def get_model(cls, name: str) -> ModelMetadata | None:
        with cls._lock:
            cls.initialize_defaults()
            return cls._models.get(name)

    @classmethod
    def get_active_llm(cls) -> ModelMetadata:
        with cls._lock:
            cls.initialize_defaults()
            model = cls._models.get(settings.OLLAMA_MODEL)
            if model is None:
                model = ModelMetadata(
                    name=settings.OLLAMA_MODEL,
                    model_type=ModelType.LLM,
                    timeout_seconds=getattr(settings, "OLLAMA_REQUEST_TIMEOUT", 900.0),
                    is_active=True,
                )
                cls._models[settings.OLLAMA_MODEL] = model
            return model

    @classmethod
    def get_active_embedding(cls) -> ModelMetadata:
        with cls._lock:
            cls.initialize_defaults()
            model = cls._models.get(settings.EMBEDDING_MODEL)
            if model is None:
                model = ModelMetadata(
                    name=settings.EMBEDDING_MODEL,
                    model_type=ModelType.EMBEDDING,
                    dimension=getattr(settings, "OLLAMA_EMBEDDING_EXPECTED_DIMENSION", 768),
                    timeout_seconds=getattr(settings, "OLLAMA_EMBED_TIMEOUT_SECONDS", 60.0),
                    is_active=True,
                )
                cls._models[settings.EMBEDDING_MODEL] = model
            return model

    @classmethod
    def record_probe(cls, name: str, healthy: bool, latency_ms: float = 0.0) -> None:
        """Record model health probe result."""
        with cls._lock:
            cls.initialize_defaults()
            model = cls._models.get(name)
            if model is None:
                return
            model.last_probe_at = time.time()
            model.last_latency_ms = round(latency_ms, 2)
            if healthy:
                model.health_status = ModelHealthStatus.HEALTHY
                model.probe_fail_count = 0
            else:
                model.probe_fail_count += 1
                model.health_status = (
                    ModelHealthStatus.UNREACHABLE if model.probe_fail_count >= 3 else ModelHealthStatus.DEGRADED
                )
                logger.warning(
                    f"[MODEL_REGISTRY] Probe failed for model '{name}' (fails={model.probe_fail_count}, status={model.health_status})"
                )

    @classmethod
    def get_all_models(cls) -> list[dict[str, Any]]:
        with cls._lock:
            cls.initialize_defaults()
            return [
                {
                    "name": m.name,
                    "type": m.model_type.value,
                    "dimension": m.dimension,
                    "context_window": m.context_window,
                    "timeout_seconds": m.timeout_seconds,
                    "is_active": m.is_active,
                    "health_status": m.health_status.value,
                    "last_probe_at": m.last_probe_at,
                    "last_latency_ms": m.last_latency_ms,
                    "probe_fail_count": m.probe_fail_count,
                }
                for m in cls._models.values()
            ]
