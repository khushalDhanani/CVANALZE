from __future__ import annotations
from datetime import datetime
from pathlib import Path

from typing import List, Set, Dict, Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "CV Analyzer"
    VERSION: str = "0.1.0"
    ALLOWED_ORIGINS: List[str] = []
    CORS_ALLOW_CREDENTIALS: bool = False
    APP_ENVIRONMENT: str = "development"
    AUTH_ENABLED: bool = False
    RECRUITER_API_KEYS: list[str] = []
    ADMINISTRATOR_API_KEYS: list[str] = []
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
    RQ_JOB_TIMEOUT_SECONDS: int = 900
    RQ_RESULT_TTL_SECONDS: int = 604800
    RQ_MAX_RETRIES: int = 2
    RQ_RETRY_INTERVAL_SECONDS: int = 30
    RQ_DEVELOPMENT_FALLBACK_ENABLED: bool = True
    PROCESSING_JOB_TTL_SECONDS: int = 604800
    PROCESSING_JOB_LOCK_TIMEOUT_SECONDS: int = 1200
    REDIS_LOCK_TIMEOUT_SECONDS: int = 120
    REDIS_LOCK_BLOCKING_TIMEOUT_SECONDS: int = 10
    JOB_NOT_FOUND_COMPATIBILITY_UNTIL: Optional[datetime] = None
    MAX_FILE_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
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
    UPLOADS_DIR: Path = Path("uploads")
    RESULTS_DIR: Path = Path("uploads/results")

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
    PERFORMANCE_L1_CACHE_MAX_SIZE: int = 5000
    PERFORMANCE_L1_CACHE_TTL_SECONDS: float = 3600.0
    EXTRACTION_TIMEOUT_SECONDS: float = 300.0
    EXTRACTION_PARSER_VERSION: str = "1.0.0"
    EXTRACTION_SCHEMA_VERSION: str = "2.0.0"
    AUTO_OCR_MIN_TEXT_CHARS: int = 100
    DOCUMENT_PARSER_WORKERS: int = 1
    DOCUMENT_TABLE_STRUCTURE_ENABLED: bool = True
    PREFER_NATIVE_TEXT_EXTRACTION: bool = False

    # LLM & Semantic Match Configuration
    LLM_ENABLED: bool = True
    OLLAMA_BASE_URL: str = ""
    OLLAMA_MODEL: str = "qwen3:4b"  # or qwen2.5:3b etc based on what's available
    OLLAMA_REQUEST_TIMEOUT: float = 300.0
    OLLAMA_CONNECT_TIMEOUT_SECONDS: float = 3.0
    OLLAMA_TAGS_TIMEOUT_SECONDS: float = 3.0
    OLLAMA_GENERATE_TIMEOUT_SECONDS: float = 300.0
    OLLAMA_EMBED_TIMEOUT_SECONDS: float = 30.0
    OLLAMA_UNLOAD_TIMEOUT_SECONDS: float = 10.0
    OLLAMA_MAX_RETRIES: int = 0
    OLLAMA_RETRY_BACKOFF_SECONDS: float = 0.5
    OLLAMA_KEEP_ALIVE: str = "1m"
    OLLAMA_UNLOAD_ON_SHUTDOWN: bool = True
    OLLAMA_MAX_CONNECTIONS: int = 1
    OLLAMA_MAX_KEEPALIVE_CONNECTIONS: int = 1
    OLLAMA_MAX_RESPONSE_BYTES: int = 4 * 1024 * 1024
    OLLAMA_LOCK_FILE: Path = Path("uploads/.locks/ollama.lock")
    OLLAMA_LOCK_TIMEOUT_SECONDS: float = 65.0
    OLLAMA_EMBED_BATCH_SIZE: int = 10
    OLLAMA_EMBED_MIN_SPLIT_SIZE: int = 2
    OLLAMA_EMBEDDING_EXPECTED_DIMENSION: int = 768
    OLLAMA_EMBEDDING_MAX_DIMENSION: int = 4096
    OLLAMA_LIVE_TESTS_ENABLED: bool = False
    OLLAMA_GENERATION_NUM_CTX: int = 4096
    OLLAMA_GENERATION_NUM_PREDICT: int = 1024
    OLLAMA_OPTIMIZED_NUM_PREDICT: int = 2048
    PREFILTER_TOP_K: int = 60
    OPTIMIZED_PROMPT_VERSION: str = "3.5"
    MAX_CONCURRENT_LLM_WORKERS: int = 1

    # LLM Bypass Configuration
    LLM_SKIP_MARGIN_THRESHOLD: float = 15.0
    LLM_SKIP_COVERAGE_THRESHOLD: float = 0.50

    # Embedding Configuration
    EMBEDDING_ENABLED: bool = True
    EMBEDDING_MODEL: str = "nomic-embed-text"
    SEMANTIC_RETRIEVAL_TOP_N: int = 150
    SIMILAR_CANDIDATE_THRESHOLD: float = 0.85
    SIMILAR_CANDIDATE_MAX_MATCHES: int = 5

    # Matching Logic Version (bump when scoring/ranking logic changes)
    MATCHING_VERSION: str = "1.0.0"

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

    # Training Data Configuration
    TRAINING_DATA_DIR: Path = Path("uploads/training_data")

    # Database Configuration (MSSQL Read-Only)
    MSSQL_READ_ONLY_URL: str = ""

    # Database Configuration (Postgres App Data)
    POSTGRES_APP_URL: str = ""

    # Migration Configuration
    AUTO_MIGRATE: bool = False

    @property
    def IS_PRODUCTION(self) -> bool:
        return self.APP_ENVIRONMENT.strip().lower() in {"production", "prod", "staging"}

    @property
    def AUTH_REQUIRED(self) -> bool:
        return self.AUTH_ENABLED or self.IS_PRODUCTION

    @property
    def TRUSTED_ORIGINS(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.ALLOWED_ORIGINS if origin.strip() and origin.strip() != "*"]



    @model_validator(mode="after")
    def validate_production_requirements(self) -> "Settings":
        if self.IS_PRODUCTION:
            if not self.REDIS_URL:
                raise ValueError("REDIS_URL must be configured in production environments.")
            if not self.MSSQL_READ_ONLY_URL:
                raise ValueError("MSSQL_READ_ONLY_URL is required for enterprise source data.")
            if not self.POSTGRES_APP_URL:
                raise ValueError("POSTGRES_APP_URL is required for CV Analyzer application data.")
        return self


settings = Settings()
