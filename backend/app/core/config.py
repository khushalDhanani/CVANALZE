from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    PROJECT_NAME: str = "CV Analyzer"
    VERSION: str = "0.1.0"
    ALLOWED_ORIGINS: list[str] = ["*"]
    REDIS_URL: str | None = "redis://localhost:6379/0"
    MAX_FILE_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
    ALLOWED_EXTENSIONS: set[str] = {"pdf", "docx", "doc", "txt"}
    UPLOADS_DIR: Path = Path("uploads")
    RESULTS_DIR: Path = Path("uploads/results")

    # Match Engine Configuration
    MATCH_HIGH_THRESHOLD: float = 70.0
    MATCH_MEDIUM_THRESHOLD: float = 40.0
    SKILL_WEIGHT: float = 0.60
    KEYWORD_WEIGHT: float = 0.40

    # Two-Stage Match Engine Configuration
    MANDATORY_WEIGHT: float = 0.50
    PREFERRED_WEIGHT: float = 0.35
    OPTIONAL_WEIGHT: float = 0.15
    LLM_SEMANTIC_WEIGHT: float = 0.10
    MANDATORY_FAILURE_PENALTY_PER_ITEM: float = 20.0
    MAX_SCORE_ON_MANDATORY_FAILURE: float = 65.0
    REQUIRE_FULL_EVIDENCE_FOR_100: bool = True

    # Resource Optimization & Batch Processing Configuration
    BATCH_SIZE: int = 2
    MAX_BATCH_LIMIT: int = 50
    MAX_CONCURRENT_WORKERS: int = 1
    THROTTLE_DELAY_SECONDS: float = 1.0
    EXTRACTION_TIMEOUT_SECONDS: float = 300.0
    EXTRACTION_PARSER_VERSION: str = "1.0.0"
    EXTRACTION_SCHEMA_VERSION: str = "1.0.0"
    AUTO_OCR_MIN_TEXT_CHARS: int = 100

    # LLM & Semantic Match Configuration
    LLM_ENABLED: bool = True
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3:4b"  # or qwen2.5:3b etc based on what's available
    OLLAMA_REQUEST_TIMEOUT: float = 90.0
    OLLAMA_MAX_RETRIES: int = 1
    LLM_BOOST_WEIGHT: float = 0.10
    MAX_LLM_BOOST: float = 10.0
    PREFILTER_TOP_K: int = 5
    OPTIMIZED_PROMPT_VERSION: str = "3.0"
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
