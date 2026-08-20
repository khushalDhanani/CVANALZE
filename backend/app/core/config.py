from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "CV Analyzer Enterprise"
    APP_VERSION: str = "3.0.0"
    GIT_SHA: str = ""
    ALLOWED_ORIGINS: List[str] = []
    CORS_ALLOW_CREDENTIALS: bool = False
    APP_ENVIRONMENT: str = "development"
    AUTH_ENABLED: bool = False
    RECRUITER_API_KEYS: list[str] = []
    ADMINISTRATOR_API_KEYS: list[str] = []
    AUTH_SESSION_SIGNING_KEY: str = ""
    AUTH_SESSION_TTL_SECONDS: int = 8 * 60 * 60
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 300
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_MAX_BUCKETS: int = 10000
    MAX_JSON_REQUEST_SIZE_BYTES: int = 1024 * 1024
    MAX_CV_TEXT_LENGTH_CHARS: int = 500_000
    MAX_HR_FEEDBACK_LENGTH_CHARS: int = 10_000
    INITIALIZE_DATABASE_ON_STARTUP: bool = True
    STARTUP_CACHE_WARMUP_ENABLED: bool = True
    REDIS_URL: Optional[str] = None
    RQ_QUEUE_NAME: str = "cv-processing"
    RQ_AUXILIARY_QUEUE_NAME: str = "default"
    RQ_SHADOW_QUEUE_NAME: str = "shadow_validation"
    CV_PROCESSING_CONCURRENCY: int = 1
    CV_QUEUE_MAX_SIZE: int = 1000
    RQ_WORKER_MAX_JOBS: int = 0
    RQ_JOB_TIMEOUT_SECONDS: int = 2400
    RQ_RESULT_TTL_SECONDS: int = 604800
    RQ_MAX_RETRIES: int = 2
    RQ_RETRY_INTERVAL_SECONDS: int = 30
    RQ_MAINTENANCE_INTERVAL_SECONDS: int = 60
    SHADOW_VALIDATION_MAX_RETRIES: int = 3
    SHADOW_VALIDATION_RETRY_INTERVAL_SECONDS: int = 60
    SHADOW_VALIDATION_JOB_TIMEOUT_SECONDS: int = 600
    RULE_CONFIG_RETRY_INTERVAL_SECONDS: float = 5.0
    CV_JOB_RECONCILIATION_INTERVAL_SECONDS: int = 60
    CV_JOB_STALE_AFTER_SECONDS: int = 1200
    CV_JOB_HISTORY_HOURS: int = 24
    CV_JOB_LIST_LIMIT: int = 100
    BACKGROUND_SYNC_ENABLED: bool = True
    BACKGROUND_SYNC_INTERVAL_SECONDS: int = 900
    BACKGROUND_SYNC_JOB_TIMEOUT_SECONDS: int = 1800
    BACKGROUND_SYNC_LOCK_TIMEOUT_SECONDS: int = 3600
    INTEGRATION_SYNC_BATCH_SIZE: int = 1000
    SOURCE_FRESHNESS_MAX_AGE_SECONDS: int = 3600
    VALIDATION_METRICS_SNAPSHOT_ENABLED: bool = True
    VALIDATION_METRICS_SNAPSHOT_INTERVAL_SECONDS: int = 86400
    PROCESSING_JOB_TTL_SECONDS: int = 604800
    PROCESSING_JOB_LOCK_TIMEOUT_SECONDS: int = 1200
    PROCESSING_RECOVERY_LOCK_TIMEOUT_SECONDS: int = 30
    PROCESSING_RECOVERY_LOCK_BLOCKING_TIMEOUT_SECONDS: int = 0
    REDIS_LOCK_TIMEOUT_SECONDS: int = 120
    REDIS_LOCK_BLOCKING_TIMEOUT_SECONDS: int = 10
    REDIS_SOCKET_TIMEOUT_SECONDS: float = 30.0
    REDIS_CONNECT_TIMEOUT_SECONDS: float = 10.0
    REDIS_HEALTH_CHECK_INTERVAL_SECONDS: int = 30
    REDIS_AVAILABILITY_PROBE_TIMEOUT_SECONDS: float = 1.0
    REDIS_SCAN_COUNT: int = 1000
    CACHE_FILE_LOCK_TIMEOUT_SECONDS: float = 5.0
    SCHEDULER_REDIS_RETRY_DELAY_SECONDS: float = 5.0
    CONFIG_INVALIDATION_RETRY_SECONDS: float = 5.0
    API_STREAM_POLL_TIMEOUT_SECONDS: float = 1.0
    API_STREAM_IDLE_SLEEP_SECONDS: float = 0.1
    JOB_CACHE_STALENESS_TTL_SECONDS: float = 30.0
    DEFAULT_BATCH_CANDIDATE_LIMIT: int = 10
    DEFAULT_API_LIST_LIMIT: int = 100
    DEFAULT_CANDIDATE_SEARCH_LIMIT: int = 50
    BATCH_CANDIDATE_LIMIT_OPTIONS: List[int] = [5, 10, 20, 30]
    RECOMMENDED_POLL_INTERVAL_MS: int = 3000
    RECOMMENDED_MAX_POLL_ATTEMPTS: int = 1200
    DOCUMENT_PARSER_DISPLAY_NAME: str = "Docling"
    OCR_ENGINE_DISPLAY_NAME: str = "RapidOCR"
    LLM_PROVIDER_DISPLAY_NAME: str = "Ollama local LLM"
    VECTOR_STORE_DISPLAY_NAME: str = "PostgreSQL pgvector"
    PROCESSING_PIPELINE_STAGES: List[Dict[str, str]] = [
        {"id": "upload", "label": "Upload CV", "description": "Transferring document to processing server"},
        {"id": "validation", "label": "Validation", "description": "Verifying file integrity and format compatibility"},
        {"id": "parsing", "label": "Document Parsing", "description": "Extracting structured layout and OCR text elements"},
        {"id": "extraction", "label": "Profile Extraction", "description": "Structuring candidate profile, skills, and work history"},
        {"id": "ai_analysis", "label": "AI Reasoning", "description": "Performing semantic analysis and skill inference"},
        {"id": "matching", "label": "Job Matching", "description": "Evaluating the candidate against active vacancies"},
        {"id": "ranking", "label": "Score Ranking", "description": "Calculating configured component weights and penalties"},
        {"id": "complete", "label": "Analysis Ready", "description": "Candidate evaluation and match scores are available"},
    ]
    JOB_NOT_FOUND_COMPATIBILITY_UNTIL: Optional[datetime] = None
    MAX_FILE_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
    MAX_UPLOAD_FILES_PER_SELECTION: int = 10
    UPLOAD_READ_CHUNK_SIZE_BYTES: int = 1024 * 1024
    UPLOAD_FILENAME_MAX_CHARS: int = 120
    ALLOWED_EXTENSIONS: Set[str] = {"pdf", "docx"}
    ALLOWED_MIME_TYPES: Dict[str, List[str]] = {
        "pdf": ["application/pdf", "application/x-pdf", "application/octet-stream"],
        "docx": [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
            "application/x-zip-compressed",
            "application/octet-stream",
        ],
    }
    MAX_DOCX_EXPANDED_SIZE_BYTES: int = 75 * 1024 * 1024
    MAX_DOCX_ENTRIES: int = 2000
    MAX_DOCX_COMPRESSION_RATIO: float = 200.0
    MAX_PDF_PAGES: int = 100
    MAX_PDF_XREF_OBJECTS: int = 10000
    MAX_PDF_IMAGES: int = 1000
    MAX_PDF_TOTAL_PAGE_AREA_POINTS: float = 500_000_000.0
    MAX_PDF_EMBEDDED_FILES: int = 0
    RAW_UPLOAD_RETENTION_DAYS: int = 30
    RAW_UPLOAD_DELETE_ON_SUCCESS: bool = False
    RAW_UPLOAD_DELETE_ON_FAILURE: bool = False
    APP_DATA_ROOT: Path = Field(
        default_factory=lambda: (Path(__file__).resolve().parents[2] / "uploads").resolve()
    )
    UPLOADS_DIR: Path | None = None
    RESULTS_DIR: Path | None = None
    LOCK_DIR: Path | None = None
    TRAINING_DATA_DIR: Path | None = None

    # Cutover Configuration
    MSSQL_CUTOVER_COMPLETE: bool = False

    # Match Engine Configuration
    SHADOW_MODE_ENABLED: bool = False
    
    # Resource Optimization & Batch Processing Configuration
    BATCH_SIZE: int = 2
    MAX_BATCH_LIMIT: int = 50
    MAX_CONCURRENT_WORKERS: int = 1
    THROTTLE_DELAY_SECONDS: float = 1.0
    CACHE_TTL_DOC_SECONDS: int = 2592000
    CACHE_TTL_LLM_SECONDS: int = 2592000
    CACHE_TTL_CONFIG_SECONDS: int = 3600
    CACHE_TTL_EMBEDDING_SECONDS: int = 2592000
    CACHE_TTL_MATCH_RESULT_SECONDS: int = 604800
    CACHE_TTL_VACANCY_SECONDS: int = 3600
    CACHE_TTL_MASTER_DATA_SECONDS: int = 3600
    CACHE_LRU_CAPACITY: int = 128
    CACHE_VERSION: str = "v1.5.0"
    PERFORMANCE_L1_CACHE_MAX_SIZE: int = 5000
    PERFORMANCE_L1_CACHE_TTL_SECONDS: float = 3600.0
    EXTRACTION_TIMEOUT_SECONDS: float = 900.0
    SCANNED_EXTRACTION_TIMEOUT_SECONDS: float = 1800.0
    EXTRACTION_PARSER_VERSION: str = "1.0.0"
    EXTRACTION_SCHEMA_VERSION: str = "2.0.0"
    EXPERIENCE_CALCULATOR_VERSION: str = "2.0.0"
    TAXONOMY_VERSION: str = "1.5.0"
    MATCHING_VERSION: str = "3.0.7"
    PARSING_VERSION: str = "1.5.0"
    CV_SCHEMA_VERSION: str = "2.1"
    AUTO_OCR_MIN_TEXT_CHARS: int = 100

    DOCUMENT_PARSER_WORKERS: int = 1
    DOCUMENT_TABLE_STRUCTURE_ENABLED: bool = True
    PREFER_NATIVE_TEXT_EXTRACTION: bool = False

    # LLM & Semantic Match Configuration
    LLM_ENABLED: bool = True
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    OLLAMA_THINKING_MODEL_FAMILIES: Set[str] = {"deepseek-r1", "gpt-oss", "qwen3", "qwen3.5"}
    OLLAMA_GENERATION_TEMPERATURE: float = 0.0
    OLLAMA_OPTIMIZED_TOP_P: float = 0.9
    OLLAMA_REQUEST_TIMEOUT: float = 900.0
    OLLAMA_CONNECT_TIMEOUT_SECONDS: float = 5.0
    OLLAMA_TAGS_TIMEOUT_SECONDS: float = 5.0
    OLLAMA_GENERATE_TIMEOUT_SECONDS: float = 1800.0
    OLLAMA_EMBED_TIMEOUT_SECONDS: float = 60.0
    OLLAMA_UNLOAD_TIMEOUT_SECONDS: float = 15.0
    OLLAMA_MAX_RETRIES: int = 0
    OLLAMA_RETRY_BACKOFF_SECONDS: float = 0.5
    OLLAMA_RETRY_JITTER_SECONDS: float = 0.1
    OLLAMA_KEEP_ALIVE: str = "30m"
    OLLAMA_RESIDENCY_ENABLED: bool = True
    OLLAMA_UNLOAD_ON_SHUTDOWN: bool = True
    OLLAMA_MAX_CONNECTIONS: int = 1
    OLLAMA_MAX_KEEPALIVE_CONNECTIONS: int = 1
    OLLAMA_MAX_RESPONSE_BYTES: int = 4 * 1024 * 1024
    OLLAMA_LOCK_FILE: Path | None = None
    OLLAMA_LOCK_TIMEOUT_SECONDS: float = 1800.0
    OLLAMA_CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 3
    OLLAMA_CIRCUIT_BREAKER_RESET_SECONDS: float = 60.0
    OLLAMA_EMBED_BATCH_SIZE: int = 10
    OLLAMA_EMBED_MIN_SPLIT_SIZE: int = 2
    OLLAMA_EMBEDDING_EXPECTED_DIMENSION: int = 768
    OLLAMA_EMBEDDING_MAX_DIMENSION: int = 4096
    OLLAMA_LIVE_TESTS_ENABLED: bool = False
    OLLAMA_GENERATION_NUM_CTX: int = 8192
    OLLAMA_GENERATION_NUM_PREDICT: int = 1536
    OLLAMA_OPTIMIZED_NUM_CTX: int = 16384
    OLLAMA_OPTIMIZED_NUM_PREDICT: int = 3072
    PREFILTER_TOP_K: int = 60
    LLM_TOP_N: int = 6
    LLM_CV_MAX_CHARS: int = 4000          # Deprecated compatibility setting; token budgets are authoritative
    LLM_PROFILE_MAX_CHARS: int = 7500     # Deprecated compatibility setting; token budgets are authoritative
    LLM_CONTEXT_CV_TOKEN_BUDGET: int = 1200
    LLM_PROFILE_TOKEN_BUDGET: int = 1900
    LLM_PROMPT_SECURITY_ENABLED: bool = True
    LLM_DEIDENTIFY_MATCHING_INPUTS: bool = True
    LLM_GROUNDING_ENABLED: bool = True
    LLM_STRUCTURED_REPAIR_ENABLED: bool = True
    LLM_TRACE_ENABLED: bool = True
    LLM_TRACE_RETENTION_DAYS: int = 30
    LLM_SHADOW_QUALITY_ENABLED: bool = True
    LLM_CONFIDENCE_CALIBRATION_PATH: Path = Field(default_factory=lambda: Path(os.getenv("LLM_CONFIDENCE_CALIBRATION_PATH", str(Path(__file__).resolve().parent.parent / "data" / "evaluations" / "confidence_calibration.json"))).resolve())
    OPTIMIZED_PROMPT_VERSION: str = "4.0"

    # LLM Bypass Configuration
    LLM_SKIP_MARGIN_THRESHOLD: float = 15.0
    LLM_SKIP_COVERAGE_THRESHOLD: float = 0.50

    # Embedding & Hybrid Search Configuration
    EMBEDDING_ENABLED: bool = True
    EMBEDDING_MODEL: str = "nomic-embed-text"
    SEMANTIC_RETRIEVAL_TOP_N: int = 150
    SIMILAR_CANDIDATE_THRESHOLD: float = 0.85
    SIMILAR_CANDIDATE_MAX_MATCHES: int = 5
    HNSW_EF_SEARCH: int = 100
    HYBRID_RETRIEVAL_ALPHA: float = 0.5
    RRF_K_CONSTANT: float = 60.0

    # Recommendation Engine Configuration
    CAREER_TRANSITION_MIN_OVERLAP: float = 40.0
    CAREER_TRANSITION_MAX_SCORE: float = 95.0
    MAX_RECOMMENDED_VACANCIES: int = 5
    MAX_RELATED_SKILLS: int = 8
    MAX_RECOMMENDED_CERTS: int = 4
    MAX_MISSING_QUALS: int = 3
    MAX_CAREER_TRANSITIONS: int = 3
    EXPERIENCE_BANDS: Dict[str, float] = {
        "Senior": 5.0,
        "Mid-Level": 2.0,
        "Junior": 0.0,
    }

    # Database Configuration (MSSQL Read-Only)
    MSSQL_READ_ONLY_URL: str = ""
    MSSQL_READONLY_ENFORCEMENT: bool = True
    MSSQL_POOL_SIZE: int = 10
    MSSQL_MAX_OVERFLOW: int = 20
    MSSQL_POOL_TIMEOUT: float = 30.0

    # Database Configuration (Postgres App Data)
    POSTGRES_APP_URL: str = ""
    POSTGRES_POOL_SIZE: int = 10
    POSTGRES_MAX_OVERFLOW: int = 20
    POSTGRES_POOL_TIMEOUT: float = 30.0
    POSTGRES_SSL_MODE: str = "prefer"

    # Migration Configuration
    AUTO_MIGRATE: bool = False

    @property
    def IS_PRODUCTION(self) -> bool:
        return self.APP_ENVIRONMENT.strip().lower() in {"production", "prod", "staging"}

    @property
    def AUTH_REQUIRED(self) -> bool:
        return self.AUTH_ENABLED

    @property
    def VERSION(self) -> str:
        """Compatibility alias for the canonical application version."""
        return self.APP_VERSION

    @property
    def TRUSTED_ORIGINS(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.ALLOWED_ORIGINS if origin.strip() and origin.strip() != "*"]

    @property
    def LEGACY_UPLOADS_DIR(self) -> Path:
        return (self.APP_DATA_ROOT / "uploads").resolve()

    @property
    def LEGACY_RESULTS_DIR(self) -> Path:
        return (self.LEGACY_UPLOADS_DIR / "results").resolve()



    @model_validator(mode="after")
    def validate_production_requirements(self) -> "Settings":
        self.GIT_SHA = self.GIT_SHA.strip() or "unknown"
        self.APP_DATA_ROOT = self.APP_DATA_ROOT.resolve()
        self.UPLOADS_DIR = (self.UPLOADS_DIR or self.APP_DATA_ROOT).resolve()
        self.RESULTS_DIR = (self.RESULTS_DIR or self.UPLOADS_DIR / "results").resolve()
        self.LOCK_DIR = (self.LOCK_DIR or self.APP_DATA_ROOT / ".locks").resolve()
        self.TRAINING_DATA_DIR = (
            self.TRAINING_DATA_DIR or self.APP_DATA_ROOT / "training_data"
        ).resolve()
        self.OLLAMA_LOCK_FILE = (
            self.OLLAMA_LOCK_FILE or self.LOCK_DIR / "ollama.lock"
        ).resolve()

        if self.CV_PROCESSING_CONCURRENCY != 1:
            raise ValueError("CV_PROCESSING_CONCURRENCY must be 1; parallel CV execution is not supported.")
        if self.CV_QUEUE_MAX_SIZE < 1:
            raise ValueError("CV_QUEUE_MAX_SIZE must be at least 1.")
        if self.RULE_CONFIG_RETRY_INTERVAL_SECONDS <= 0:
            raise ValueError("RULE_CONFIG_RETRY_INTERVAL_SECONDS must be greater than zero.")
        if self.SHADOW_VALIDATION_MAX_RETRIES < 0:
            raise ValueError("SHADOW_VALIDATION_MAX_RETRIES must not be negative.")
        if min(
            self.SHADOW_VALIDATION_RETRY_INTERVAL_SECONDS,
            self.SHADOW_VALIDATION_JOB_TIMEOUT_SECONDS,
            self.REDIS_AVAILABILITY_PROBE_TIMEOUT_SECONDS,
            self.REDIS_SOCKET_TIMEOUT_SECONDS,
            self.REDIS_CONNECT_TIMEOUT_SECONDS,
            self.REDIS_HEALTH_CHECK_INTERVAL_SECONDS,
            self.REDIS_SCAN_COUNT,
            self.CACHE_FILE_LOCK_TIMEOUT_SECONDS,
            self.SCHEDULER_REDIS_RETRY_DELAY_SECONDS,
            self.CONFIG_INVALIDATION_RETRY_SECONDS,
            self.API_STREAM_POLL_TIMEOUT_SECONDS,
            self.API_STREAM_IDLE_SLEEP_SECONDS,
            self.JOB_CACHE_STALENESS_TTL_SECONDS,
            self.DEFAULT_BATCH_CANDIDATE_LIMIT,
            self.DEFAULT_API_LIST_LIMIT,
            self.DEFAULT_CANDIDATE_SEARCH_LIMIT,
            self.RECOMMENDED_POLL_INTERVAL_MS,
            self.RECOMMENDED_MAX_POLL_ATTEMPTS,
            self.MAX_UPLOAD_FILES_PER_SELECTION,
            self.INTEGRATION_SYNC_BATCH_SIZE,
            self.SOURCE_FRESHNESS_MAX_AGE_SECONDS,
            self.PROCESSING_RECOVERY_LOCK_TIMEOUT_SECONDS,
        ) <= 0:
            raise ValueError("Queue, Redis, sync, freshness, and recovery controls must be greater than zero.")
        if self.PROCESSING_RECOVERY_LOCK_BLOCKING_TIMEOUT_SECONDS < 0:
            raise ValueError("PROCESSING_RECOVERY_LOCK_BLOCKING_TIMEOUT_SECONDS must not be negative.")
        if self.DEFAULT_BATCH_CANDIDATE_LIMIT > self.MAX_BATCH_LIMIT:
            raise ValueError("DEFAULT_BATCH_CANDIDATE_LIMIT must not exceed MAX_BATCH_LIMIT.")
        if (
            not self.BATCH_CANDIDATE_LIMIT_OPTIONS
            or any(option <= 0 or option > self.MAX_BATCH_LIMIT for option in self.BATCH_CANDIDATE_LIMIT_OPTIONS)
            or self.DEFAULT_BATCH_CANDIDATE_LIMIT not in self.BATCH_CANDIDATE_LIMIT_OPTIONS
        ):
            raise ValueError(
                "BATCH_CANDIDATE_LIMIT_OPTIONS must contain the default and stay within MAX_BATCH_LIMIT."
            )
        if not self.ALLOWED_EXTENSIONS or any(
            not self.ALLOWED_MIME_TYPES.get(extension)
            for extension in self.ALLOWED_EXTENSIONS
        ):
            raise ValueError("Every allowed upload extension must have at least one configured MIME type.")
        pipeline_ids = [stage.get("id", "").strip() for stage in self.PROCESSING_PIPELINE_STAGES]
        if (
            not pipeline_ids
            or any(
                not stage.get("id", "").strip()
                or not stage.get("label", "").strip()
                or not stage.get("description", "").strip()
                for stage in self.PROCESSING_PIPELINE_STAGES
            )
            or len(set(pipeline_ids)) != len(pipeline_ids)
        ):
            raise ValueError("PROCESSING_PIPELINE_STAGES must contain unique, complete stage definitions.")
        if self.LLM_ENABLED or self.EMBEDDING_ENABLED:
            parsed_ollama_url = urlsplit(self.OLLAMA_BASE_URL.strip())
            if parsed_ollama_url.scheme not in {"http", "https"} or not parsed_ollama_url.netloc:
                raise ValueError("OLLAMA_BASE_URL must be an absolute HTTP or HTTPS URL when Ollama features are enabled.")
        if self.LLM_ENABLED and not self.OLLAMA_MODEL.strip():
            raise ValueError("OLLAMA_MODEL must be configured when LLM generation is enabled.")
        if self.EMBEDDING_ENABLED and not self.EMBEDDING_MODEL.strip():
            raise ValueError("EMBEDDING_MODEL must be configured when embeddings are enabled.")
        ollama_timeouts = (
            self.OLLAMA_REQUEST_TIMEOUT,
            self.OLLAMA_CONNECT_TIMEOUT_SECONDS,
            self.OLLAMA_TAGS_TIMEOUT_SECONDS,
            self.OLLAMA_GENERATE_TIMEOUT_SECONDS,
            self.OLLAMA_EMBED_TIMEOUT_SECONDS,
            self.OLLAMA_UNLOAD_TIMEOUT_SECONDS,
            self.OLLAMA_LOCK_TIMEOUT_SECONDS,
            self.OLLAMA_CIRCUIT_BREAKER_RESET_SECONDS,
        )
        if min(ollama_timeouts) <= 0:
            raise ValueError("Ollama request, operation, lock, and circuit-breaker timeouts must be greater than zero.")
        if self.OLLAMA_MAX_RETRIES < 0 or self.OLLAMA_RETRY_BACKOFF_SECONDS < 0 or self.OLLAMA_RETRY_JITTER_SECONDS < 0:
            raise ValueError("Ollama retry count, backoff, and jitter must not be negative.")
        if not 0.0 <= self.OLLAMA_GENERATION_TEMPERATURE <= 2.0:
            raise ValueError("OLLAMA_GENERATION_TEMPERATURE must be between 0 and 2.")
        if not 0.0 < self.OLLAMA_OPTIMIZED_TOP_P <= 1.0:
            raise ValueError("OLLAMA_OPTIMIZED_TOP_P must be greater than 0 and at most 1.")
        if min(self.OLLAMA_MAX_CONNECTIONS, self.OLLAMA_MAX_KEEPALIVE_CONNECTIONS, self.OLLAMA_MAX_RESPONSE_BYTES) <= 0:
            raise ValueError("Ollama connection limits and maximum response size must be greater than zero.")
        if self.OLLAMA_MAX_KEEPALIVE_CONNECTIONS > self.OLLAMA_MAX_CONNECTIONS:
            raise ValueError("OLLAMA_MAX_KEEPALIVE_CONNECTIONS must not exceed OLLAMA_MAX_CONNECTIONS.")
        if min(self.OLLAMA_CIRCUIT_BREAKER_FAILURE_THRESHOLD, self.OLLAMA_EMBED_BATCH_SIZE, self.OLLAMA_EMBED_MIN_SPLIT_SIZE) <= 0:
            raise ValueError("Ollama circuit-breaker threshold and embedding batch limits must be greater than zero.")
        if self.OLLAMA_EMBEDDING_EXPECTED_DIMENSION < 0 or self.OLLAMA_EMBEDDING_MAX_DIMENSION <= 0:
            raise ValueError("Ollama embedding dimensions must use a non-negative expected value and a positive maximum.")
        if self.OLLAMA_EMBEDDING_EXPECTED_DIMENSION > self.OLLAMA_EMBEDDING_MAX_DIMENSION:
            raise ValueError("OLLAMA_EMBEDDING_EXPECTED_DIMENSION must not exceed OLLAMA_EMBEDDING_MAX_DIMENSION.")
        if min(self.OLLAMA_GENERATION_NUM_CTX, self.OLLAMA_GENERATION_NUM_PREDICT, self.OLLAMA_OPTIMIZED_NUM_CTX, self.OLLAMA_OPTIMIZED_NUM_PREDICT) <= 0:
            raise ValueError("Ollama generation context and output limits must be greater than zero.")
        if self.OLLAMA_GENERATION_NUM_PREDICT >= self.OLLAMA_GENERATION_NUM_CTX:
            raise ValueError("OLLAMA_GENERATION_NUM_PREDICT must be smaller than OLLAMA_GENERATION_NUM_CTX.")
        if self.OLLAMA_OPTIMIZED_NUM_PREDICT >= self.OLLAMA_OPTIMIZED_NUM_CTX:
            raise ValueError("OLLAMA_OPTIMIZED_NUM_PREDICT must be smaller than OLLAMA_OPTIMIZED_NUM_CTX.")
        if self.EXTRACTION_TIMEOUT_SECONDS <= 0 or self.SCANNED_EXTRACTION_TIMEOUT_SECONDS <= 0:
            raise ValueError("Document extraction timeouts must be greater than zero.")
        if max(self.EXTRACTION_TIMEOUT_SECONDS, self.SCANNED_EXTRACTION_TIMEOUT_SECONDS) >= self.RQ_JOB_TIMEOUT_SECONDS:
            raise ValueError("Document extraction timeouts must remain below RQ_JOB_TIMEOUT_SECONDS.")
        if self.IS_PRODUCTION:
            if not self.TRUSTED_ORIGINS:
                raise ValueError("ALLOWED_ORIGINS must include at least one trusted origin in production.")
            if self.GIT_SHA == "unknown":
                raise ValueError("GIT_SHA must be injected in production environments.")
            if not self.MSSQL_READONLY_ENFORCEMENT:
                raise ValueError("MSSQL_READONLY_ENFORCEMENT must be true in production environments.")
            if not self.REDIS_URL:
                raise ValueError("REDIS_URL must be configured in production environments.")
            if not self.MSSQL_READ_ONLY_URL:
                raise ValueError("MSSQL_READ_ONLY_URL is required for enterprise source data.")
            if not self.POSTGRES_APP_URL:
                raise ValueError("POSTGRES_APP_URL is required for CV Analyzer application data.")
            if self.AUTH_ENABLED and not (
                self.RECRUITER_API_KEYS or self.ADMINISTRATOR_API_KEYS
            ):
                raise ValueError("At least one recruiter or administrator API key is required when authentication is enabled.")
            if self.AUTH_ENABLED and (not self.AUTH_SESSION_SIGNING_KEY or self.AUTH_SESSION_SIGNING_KEY.strip().lower() in {"change_me", "default_secret_key", "secret", "123456"}):
                raise ValueError("AUTH_SESSION_SIGNING_KEY must be configured with a secure non-default secret in production.")

            if "postgres:postgres@" in self.POSTGRES_APP_URL.lower():
                raise ValueError("POSTGRES_APP_URL must not use default local development credentials in production.")
            if self.REDIS_URL.startswith(("redis://localhost", "redis://127.0.0.1")):
                raise ValueError("REDIS_URL must not use default local development endpoint in production.")
            if "sa:sa@" in self.MSSQL_READ_ONLY_URL.lower():
                raise ValueError("MSSQL_READ_ONLY_URL must not use default local development credentials in production.")
            if self.POSTGRES_SSL_MODE in {"disable", "allow"}:
                raise ValueError("POSTGRES_SSL_MODE must require encryption (require, verify-ca, or verify-full) in production.")
        try:
            self.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
            self.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return self


settings = Settings()
