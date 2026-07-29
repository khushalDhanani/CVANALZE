import time
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
        pdf_type: str = "NON_PDF",
        parser_used: str = "docling_fast",
        ocr_decision: str = "SKIPPED_TEXT_PRESENT",
        stage_metrics: dict[str, Any] | None = None,
    ):
        self.markdown = markdown
        self.structured_doc = structured_doc
        self.page_count = page_count
        self.is_scanned = is_scanned
        self.ocr_applied = ocr_applied
        self.pdf_type = pdf_type
        self.parser_used = parser_used
        self.ocr_decision = ocr_decision
        self.stage_metrics = stage_metrics or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "markdown": self.markdown,
            "structured_doc": self.structured_doc,
            "page_count": self.page_count,
            "is_scanned": self.is_scanned,
            "ocr_applied": self.ocr_applied,
            "pdf_type": self.pdf_type,
            "parser_used": self.parser_used,
            "ocr_decision": self.ocr_decision,
            "stage_metrics": self.stage_metrics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExtractionResult":
        return cls(
            markdown=data["markdown"],
            structured_doc=data.get("structured_doc", {}),
            page_count=data.get("page_count", 1),
            is_scanned=data.get("is_scanned", False),
            ocr_applied=data.get("ocr_applied", False),
            pdf_type=data.get("pdf_type", "NON_PDF"),
            parser_used=data.get("parser_used", "docling_fast"),
            ocr_decision=data.get("ocr_decision", "SKIPPED_TEXT_PRESENT"),
            stage_metrics=data.get("stage_metrics", {}),
        )


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


def _classify_pdf(content: bytes) -> tuple[str, str, int, bool]:
    """
    Inspect PDF using PyMuPDF (fitz) to detect native text and images,
    and classify document as TEXT_PDF, HYBRID_PDF, or SCANNED_PDF.
    Returns tuple: (pdf_type, native_text, native_char_count, has_images)
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=content, filetype="pdf")
        page_texts = [page.get_text() for page in doc]
        native_text = "\n".join(page_texts).strip()
        native_char_count = len(native_text)
        has_images = any(len(page.get_images()) > 0 for page in doc)

        if native_char_count >= 100 and not has_images:
            pdf_type = "TEXT_PDF"
        elif native_char_count >= 50:
            pdf_type = "HYBRID_PDF"
        else:
            pdf_type = "SCANNED_PDF"

        return pdf_type, native_text, native_char_count, has_images
    except Exception as exc:
        logger.warning(f"PyMuPDF PDF classification failed: {exc}")
        return "UNKNOWN_PDF", "", 0, False


_parser_thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="docling_parser")


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
            f"Starting DocumentParser extraction pipeline for '{filename}' ({len(content)} bytes)..."
        )

        # Stage 1: Detect PDF Type & Extract Native Selectable Text
        pdf_type = "NON_PDF"
        native_pdf_text = ""
        native_char_count = 0
        has_images = False
        if extension == "pdf":
            pdf_type, native_pdf_text, native_char_count, has_images = _classify_pdf(content)
            logger.info(
                f"[STAGE 1: PDF TYPE] '{filename}': type={pdf_type}, native_chars={native_char_count}, has_images={has_images}"
            )

        # Stage 2: Primary Extractor (Docling Fast Converter - No OCR)
        t_fast_start = time.perf_counter()
        doc_stream = DocumentStream(name=filename, stream=BytesIO(content))
        ocr_applied = False
        docling_doc = None
        fast_markdown_text = ""
        fast_duration_ms = 0.0

        try:
            conv_result = _fast_converter.convert(doc_stream)
            docling_doc = conv_result.document
            fast_markdown_text = docling_doc.export_to_markdown().strip() if docling_doc else ""
            fast_duration_ms = round((time.perf_counter() - t_fast_start) * 1000.0, 2)
            logger.info(
                f"[STAGE 2: DOCLING FAST] '{filename}': extracted_chars={len(fast_markdown_text)}, duration={fast_duration_ms}ms"
            )
        except Exception as exc:
            fast_duration_ms = round((time.perf_counter() - t_fast_start) * 1000.0, 2)
            logger.warning(f"[STAGE 2: DOCLING FAST] Conversion error for '{filename}': {exc} ({fast_duration_ms}ms)")
            fast_markdown_text = ""

        # Stage 3 & 4: Selective OCR Decision & Execution
        ocr_markdown_text = ""
        ocr_duration_ms = 0.0
        fast_len = len(fast_markdown_text)

        if extension != "pdf":
            ocr_decision = "SKIPPED_NON_PDF"
        elif pdf_type in ("TEXT_PDF", "HYBRID_PDF") and (fast_len >= 50 or native_char_count >= 50):
            ocr_decision = "SKIPPED_TEXT_PRESENT"
        elif fast_len >= settings.AUTO_OCR_MIN_TEXT_CHARS or native_char_count >= settings.AUTO_OCR_MIN_TEXT_CHARS:
            ocr_decision = "SKIPPED_SUFFICIENT_TEXT"
        else:
            ocr_decision = "INVOKED_SPARSE_TEXT"

        if ocr_decision == "INVOKED_SPARSE_TEXT":
            logger.info(
                f"[STAGE 3: OCR DECISION] '{filename}': decision={ocr_decision}. "
                f"Triggering RapidOCR (pdf_type={pdf_type}, fast_docling={fast_len} chars, native={native_char_count} chars)..."
            )
            t_ocr_start = time.perf_counter()
            try:
                doc_stream_ocr = DocumentStream(name=filename, stream=BytesIO(content))
                conv_result = _get_ocr_converter().convert(doc_stream_ocr)
                ocr_duration_ms = round((time.perf_counter() - t_ocr_start) * 1000.0, 2)
                if conv_result and conv_result.document:
                    ocr_docling_doc = conv_result.document
                    ocr_markdown_text = ocr_docling_doc.export_to_markdown().strip()
                    if len(ocr_markdown_text) > len(fast_markdown_text):
                        docling_doc = ocr_docling_doc
                    ocr_applied = True
                    logger.info(
                        f"[STAGE 4: OCR EXECUTION] '{filename}': ocr_chars={len(ocr_markdown_text)}, duration={ocr_duration_ms}ms"
                    )
            except Exception as ocr_exc:
                ocr_duration_ms = round((time.perf_counter() - t_ocr_start) * 1000.0, 2)
                logger.warning(
                    f"[STAGE 4: OCR EXECUTION] RapidOCR warning for '{filename}': {ocr_exc} ({ocr_duration_ms}ms). "
                    f"Non-fatal fallback to native/fast text."
                )
        else:
            logger.info(
                f"[STAGE 3: OCR DECISION] '{filename}': decision={ocr_decision}. OCR skipped."
            )

        # Stage 5: Select Best Available Text & Validate Resume JSON
        parser_used = "docling_fast"
        final_text = fast_markdown_text

        if ocr_applied and len(ocr_markdown_text) > len(final_text):
            final_text = ocr_markdown_text
            parser_used = "docling_ocr"

        if len(final_text.strip()) < 20 and len(native_pdf_text.strip()) >= 20:
            logger.info(
                f"Using native PDF text ({len(native_pdf_text)} chars) for '{filename}' "
                f"as primary Docling output was empty or sparse."
            )
            final_text = native_pdf_text
            parser_used = "native_fitz"

        final_text_clean = final_text.strip()

        if not final_text_clean or (len(final_text_clean) < 20 and "<!-- image -->" in final_text_clean):
            logger.error(
                f"[STAGE 5: RESUME JSON] All extraction stages failed for '{filename}'. Total chars: {len(final_text_clean)}"
            )
            raise ValueError(
                f"No readable text or content could be extracted from CV document '{filename}'. "
                f"The document may be an unreadable low-quality scan or contain only non-text image elements."
            )

        structured_dict = docling_doc.export_to_dict() if docling_doc and hasattr(docling_doc, "export_to_dict") else {}
        pages_count = (
            len(docling_doc.pages)
            if docling_doc and hasattr(docling_doc, "pages") and docling_doc.pages
            else 1
        )

        is_scanned = (pdf_type == "SCANNED_PDF") or (extension == "pdf" and (
            "<!-- image -->" in final_text_clean
            or (ocr_applied and native_char_count < 50)
            or (docling_doc and hasattr(docling_doc, "pictures") and len(docling_doc.pictures) > 0)
        ))

        stage_metrics = {
            "pdf_type": pdf_type,
            "native_char_count": native_char_count,
            "has_images": has_images,
            "fast_docling_chars": fast_len,
            "fast_docling_ms": fast_duration_ms,
            "ocr_decision": ocr_decision,
            "ocr_chars": len(ocr_markdown_text),
            "ocr_ms": ocr_duration_ms,
            "final_char_count": len(final_text_clean),
            "parser_used": parser_used,
        }

        logger.info(
            f"[STAGE 5: RESUME JSON] Successful extraction for '{filename}': "
            f"type={pdf_type}, parser={parser_used}, final_chars={len(final_text_clean)}, "
            f"pages={pages_count}, scanned={is_scanned}, ocr={ocr_applied}."
        )

        return ExtractionResult(
            markdown=final_text_clean,
            structured_doc=structured_dict,
            page_count=pages_count,
            is_scanned=is_scanned,
            ocr_applied=ocr_applied,
            pdf_type=pdf_type,
            parser_used=parser_used,
            ocr_decision=ocr_decision,
            stage_metrics=stage_metrics,
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

        future = _parser_thread_pool.submit(cls.parse, filename, content)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError as exc:
            logger.error(
                f"Extraction timed out after {timeout} seconds for '{filename}'."
            )
            raise TimeoutError(
                f"Extraction timed out after {timeout} seconds for '{filename}'."
            ) from exc
