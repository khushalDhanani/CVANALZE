from datetime import datetime
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    PROJECT_NAME: str = "CV Analyzer"
    VERSION: str = "0.1.0"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:8081"]
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
    REDIS_URL: str | None = "redis://localhost:6379/0"
    RQ_QUEUE_NAME: str = "cv-processing"
    RQ_JOB_TIMEOUT_SECONDS: int = 900
    RQ_RESULT_TTL_SECONDS: int = 604800
    RQ_MAX_RETRIES: int = 2
    RQ_RETRY_INTERVAL_SECONDS: int = 30
    RQ_DEVELOPMENT_FALLBACK_ENABLED: bool = True
    PROCESSING_JOB_TTL_SECONDS: int = 604800
    PROCESSING_JOB_LOCK_TIMEOUT_SECONDS: int = 1200
    JOB_NOT_FOUND_COMPATIBILITY_UNTIL: datetime | None = None
    MAX_FILE_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
    UPLOAD_READ_CHUNK_SIZE_BYTES: int = 1024 * 1024
    UPLOAD_FILENAME_MAX_CHARS: int = 120
    ALLOWED_EXTENSIONS: set[str] = {"pdf", "docx"}
    ALLOWED_MIME_TYPES: dict[str, list[str]] = {
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

    # Match Engine Configuration
    MATCH_HIGH_THRESHOLD: float = 70.0
    MATCH_MEDIUM_THRESHOLD: float = 40.0
    LLM_SEMANTIC_WEIGHT: float = 0.10
    MANDATORY_FAILURE_PENALTY_PER_ITEM: float = 20.0
    MAX_SCORE_ON_MANDATORY_FAILURE: float = 65.0

    MATCH_COMPONENT_WEIGHTS: dict[str, float] = {
        "role": 0.15,
        "skills": 0.25,
        "experience": 0.15,
        "education": 0.10,
        "domain": 0.15,
        "technology": 0.10,
        "certification": 0.05,
        "responsibilities": 0.05,
    }

    # Resource Optimization & Batch Processing Configuration
    BATCH_SIZE: int = 2
    MAX_BATCH_LIMIT: int = 50
    MAX_CONCURRENT_WORKERS: int = 1
    THROTTLE_DELAY_SECONDS: float = 1.0
    EXTRACTION_TIMEOUT_SECONDS: float = 300.0
    EXTRACTION_PARSER_VERSION: str = "1.0.0"
    EXTRACTION_SCHEMA_VERSION: str = "2.0.0"
    AUTO_OCR_MIN_TEXT_CHARS: int = 100

    # LLM & Semantic Match Configuration
    LLM_ENABLED: bool = True
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3:4b"  # or qwen2.5:3b etc based on what's available
    OLLAMA_REQUEST_TIMEOUT: float = 90.0
    OLLAMA_MAX_RETRIES: int = 1
    OLLAMA_RETRY_BACKOFF_SECONDS: float = 0.5
    OLLAMA_KEEP_ALIVE: str = "30m"
    OLLAMA_UNLOAD_ON_SHUTDOWN: bool = False
    OLLAMA_MAX_CONNECTIONS: int = 20
    OLLAMA_MAX_KEEPALIVE_CONNECTIONS: int = 10
    LLM_BOOST_WEIGHT: float = 0.10
    MAX_LLM_BOOST: float = 10.0
    PREFILTER_TOP_K: int = 5
    OPTIMIZED_PROMPT_VERSION: str = "3.5"
    MAX_CONCURRENT_LLM_WORKERS: int = 2

    # LLM Bypass Configuration
    LLM_SKIP_MARGIN_THRESHOLD: float = 15.0
    LLM_SKIP_COVERAGE_THRESHOLD: float = 0.50

    # Embedding Configuration
    EMBEDDING_ENABLED: bool = True
    EMBEDDING_MODEL: str = "nomic-embed-text"
    SEMANTIC_RETRIEVAL_TOP_N: int = 50
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
    EXPERIENCE_BANDS: dict[str, float] = {
        "Senior": 5.0,
        "Mid-Level": 2.0,
        "Junior": 0.0,
    }

    # Training Data Configuration
    TRAINING_DATA_DIR: Path = Path("uploads/training_data")

    # Database Configuration (MSSQL)
    DB_SERVER: str = "localhost"
    DB_PORT: int = 1433
    DB_NAME: str = ""
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_ENCRYPT: bool = True
    DB_TRUST_CERT: bool = True

    # Database Configuration (Postgres)
    PG_DB_URL: str = "postgresql://postgres:postgres@localhost:5432/cv_analyzer"

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

    @property
    def DB_URL(self) -> str:
        if not self.DB_NAME:
            return ""
        # Using pyodbc and mssql+pyodbc dialect with ODBC Driver 18
        import urllib.parse

        encoded_password = urllib.parse.quote_plus(self.DB_PASSWORD)
        enc = "yes" if self.DB_ENCRYPT else "no"
        trust = "yes" if self.DB_TRUST_CERT else "no"
        return f"mssql+pyodbc://{self.DB_USER}:{encoded_password}@{self.DB_SERVER}:{self.DB_PORT}/{self.DB_NAME}?driver=ODBC+Driver+18+for+SQL+Server&Encrypt={enc}&TrustServerCertificate={trust}"


settings = Settings()
