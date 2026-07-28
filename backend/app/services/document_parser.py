from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from io import BytesIO
from typing import Any

from docling.datamodel.base_models import DocumentStream
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from app.core.config import settings
from app.core.logging import logger


class ExtractionResult:
    def __init__(
        self,
        markdown: str,
        structured_doc: dict[str, Any],
        page_count: int,
        is_scanned: bool,
        ocr_applied: bool,
    ):
        self.markdown = markdown
        self.structured_doc = structured_doc
        self.page_count = page_count
        self.is_scanned = is_scanned
        self.ocr_applied = ocr_applied


def _init_fast_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    return DocumentConverter(
        format_options={"pdf": PdfFormatOption(pipeline_options=pipeline_options)}
    )


def _init_ocr_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.ocr_options = RapidOcrOptions(force_full_page_ocr=True)
    return DocumentConverter(
        format_options={"pdf": PdfFormatOption(pipeline_options=pipeline_options)}
    )


_fast_converter = _init_fast_converter()
_ocr_converter_instance: DocumentConverter | None = None


def _get_ocr_converter() -> DocumentConverter:
    global _ocr_converter_instance
    if _ocr_converter_instance is None:
        _ocr_converter_instance = _init_ocr_converter()
    return _ocr_converter_instance


class DocumentParser:
    @classmethod
    def parse(cls, filename: str, content: bytes) -> ExtractionResult:
        if not content or len(content) == 0:
            raise ValueError("Uploaded file is empty (0 bytes).")

        if len(content) > settings.MAX_FILE_SIZE_BYTES:
            max_mb = settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)
            raise ValueError(f"File size exceeds maximum limit of {max_mb} MB.")

        if "." not in filename:
            raise ValueError("Filename must have a valid extension.")

        extension = filename.lower().rsplit(".", 1)[-1]
        if extension not in settings.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(settings.ALLOWED_EXTENSIONS))
            raise ValueError(
                f"Unsupported file extension '.{extension}'. Allowed formats: {allowed}."
            )

        import filetype
        kind = filetype.guess(content)
        if kind is not None:
            if extension == "pdf" and kind.mime != "application/pdf":
                raise ValueError("Invalid file signature. The file claims to be a PDF but the magic bytes mismatch.")
            elif extension == "docx" and kind.mime not in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"]:
                raise ValueError("Invalid file signature. The file claims to be a DOCX but the magic bytes mismatch.")
        elif extension == "pdf":
            raise ValueError("Invalid file signature. Missing PDF magic bytes.")

        logger.info(
            f"Starting Docling extraction for '{filename}' ({len(content)} bytes)..."
        )

        doc_stream = DocumentStream(name=filename, stream=BytesIO(content))
        ocr_applied = False
        
        try:
            conv_result = _fast_converter.convert(doc_stream)
            docling_doc = conv_result.document
            markdown_text = docling_doc.export_to_markdown().strip()

            # Dynamic OCR check: if PDF text is sparse (< AUTO_OCR_MIN_TEXT_CHARS), fallback to full OCR converter
            if (
                extension == "pdf"
                and len(markdown_text) < settings.AUTO_OCR_MIN_TEXT_CHARS
            ):
                logger.info(
                    f"Sparse text detected ({len(markdown_text)} chars) in '{filename}'. Re-running with OCR engine..."
                )
                doc_stream_ocr = DocumentStream(name=filename, stream=BytesIO(content))
                conv_result = _get_ocr_converter().convert(doc_stream_ocr)
                docling_doc = conv_result.document
                markdown_text = docling_doc.export_to_markdown().strip()
                ocr_applied = True

        except Exception as exc:
            logger.error(f"Docling conversion error for '{filename}': {exc}")
            raise ValueError(f"Failed to parse document '{filename}': {exc}") from exc

        if not markdown_text:
            raise ValueError(
                f"No readable text or content found in CV document '{filename}'."
            )

        structured_dict = docling_doc.export_to_dict()

        pages_count = (
            len(docling_doc.pages)
            if hasattr(docling_doc, "pages") and docling_doc.pages
            else 1
        )

        is_scanned = extension == "pdf" and (
            "<!-- image -->" in markdown_text
            or ocr_applied
            or (hasattr(docling_doc, "pictures") and len(docling_doc.pictures) > 0)
        )

        logger.info(
            f"Docling extraction successful for '{filename}': "
            f"{len(markdown_text)} chars, {pages_count} page(s), scanned={is_scanned}, ocr={ocr_applied}."
        )

        return ExtractionResult(
            markdown=markdown_text,
            structured_doc=structured_dict,
            page_count=pages_count,
            is_scanned=is_scanned,
            ocr_applied=ocr_applied,
        )

    @classmethod
    def parse_with_timeout(
        cls,
        filename: str,
        content: bytes,
        timeout_seconds: float | None = None,
    ) -> ExtractionResult:
        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.EXTRACTION_TIMEOUT_SECONDS
        )

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(cls.parse, filename, content)
            try:
                return future.result(timeout=timeout)
            except FuturesTimeoutError as exc:
                logger.error(
                    f"Extraction timed out after {timeout} seconds for '{filename}'."
                )
                raise TimeoutError(
                    f"Extraction timed out after {timeout} seconds for '{filename}'."
                ) from exc
