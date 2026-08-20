from app.core.config import settings
from app.core.rule_config_manager import PolicyRegistry
from app.schemas.capabilities import (
    ApplicationCapabilities,
    BatchCapabilities,
    ImplementationCapabilities,
    PipelineStageCapability,
    PollingCapabilities,
    SimilarityCapabilities,
    UploadCapabilities,
)


class CapabilitiesService:
    """Build the public runtime-capability contract from authoritative settings."""

    @staticmethod
    def get_capabilities() -> ApplicationCapabilities:
        similarity_policy = PolicyRegistry.resolve_snapshot().similarity
        limit_options = sorted(
            {
                option
                for option in settings.BATCH_CANDIDATE_LIMIT_OPTIONS
                if 0 < option <= settings.MAX_BATCH_LIMIT
            }
        )
        return ApplicationCapabilities(
            upload=UploadCapabilities(
                extensions=sorted(settings.ALLOWED_EXTENSIONS),
                mime_types={
                    extension: list(mime_types)
                    for extension, mime_types in sorted(settings.ALLOWED_MIME_TYPES.items())
                },
                max_size_bytes=settings.MAX_FILE_SIZE_BYTES,
                max_pdf_pages=settings.MAX_PDF_PAGES,
                max_files_per_selection=settings.MAX_UPLOAD_FILES_PER_SELECTION,
            ),
            batch=BatchCapabilities(
                limit_options=limit_options,
                default_limit=settings.DEFAULT_BATCH_CANDIDATE_LIMIT,
                max_limit=settings.MAX_BATCH_LIMIT,
            ),
            polling=PollingCapabilities(
                interval_ms=settings.RECOMMENDED_POLL_INTERVAL_MS,
                max_attempts=settings.RECOMMENDED_MAX_POLL_ATTEMPTS,
            ),
            implementation=ImplementationCapabilities(
                document_parser=settings.DOCUMENT_PARSER_DISPLAY_NAME,
                ocr_engine=settings.OCR_ENGINE_DISPLAY_NAME,
                llm_provider=settings.LLM_PROVIDER_DISPLAY_NAME,
                vector_store=settings.VECTOR_STORE_DISPLAY_NAME,
            ),
            pipeline=[PipelineStageCapability.model_validate(stage) for stage in settings.PROCESSING_PIPELINE_STAGES],
            similarity=SimilarityCapabilities(
                default_threshold=similarity_policy.domain_default_threshold,
                minimum_threshold=similarity_policy.min_similarity_threshold,
                maximum_threshold=1.0,
                default_limit=similarity_policy.domain_default_limit,
                maximum_limit=similarity_policy.domain_max_limit,
                high_band=similarity_policy.high_similarity_band,
                medium_band=similarity_policy.medium_similarity_band,
            ),
        )
