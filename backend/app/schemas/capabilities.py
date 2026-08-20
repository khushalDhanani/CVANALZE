from pydantic import BaseModel, Field


class UploadCapabilities(BaseModel):
    extensions: list[str]
    mime_types: dict[str, list[str]]
    max_size_bytes: int = Field(ge=1)
    max_pdf_pages: int = Field(ge=1)
    max_files_per_selection: int = Field(ge=1)


class BatchCapabilities(BaseModel):
    limit_options: list[int]
    default_limit: int = Field(ge=1)
    max_limit: int = Field(ge=1)


class PollingCapabilities(BaseModel):
    interval_ms: int = Field(ge=1)
    max_attempts: int = Field(ge=1)


class ImplementationCapabilities(BaseModel):
    document_parser: str
    ocr_engine: str
    llm_provider: str
    vector_store: str


class PipelineStageCapability(BaseModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ApplicationCapabilities(BaseModel):
    upload: UploadCapabilities
    batch: BatchCapabilities
    polling: PollingCapabilities
    implementation: ImplementationCapabilities
    pipeline: list[PipelineStageCapability]
