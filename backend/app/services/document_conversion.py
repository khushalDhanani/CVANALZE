from __future__ import annotations
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from io import BytesIO
from threading import Lock
from typing import Any

from docling.datamodel.base_models import DocumentStream
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling_pp_ocrv6 import PPOCRv6Options
from docling.document_converter import DocumentConverter, PdfFormatOption

from app.core.config import settings
from app.core.logging import logger
from app.services.resume_text_normalizer import ResumeTextNormalizer
from app.services.upload_service import UploadService

_OCR_ENGINE = "PP-OCRv6-Medium"


class MarkdownResult:
    def __init__(
        self,
        markdown: str,
        page_count: int,
        is_scanned: bool,
        ocr_applied: bool,
        pdf_type: str = "NON_PDF",
        parser_used: str = "docling_fast",
        ocr_decision: str = "SKIPPED_TEXT_PRESENT",
        stage_metrics: dict[str, Any] | None = None,
    ):
        self.markdown = markdown
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
            "page_count": self.page_count,
            "is_scanned": self.is_scanned,
            "ocr_applied": self.ocr_applied,
            "pdf_type": self.pdf_type,
            "parser_used": self.parser_used,
            "ocr_decision": self.ocr_decision,
            "stage_metrics": self.stage_metrics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MarkdownResult":
        return cls(
            markdown=data["markdown"],
            page_count=data.get("page_count", 1),
            is_scanned=data.get("is_scanned", False),
            ocr_applied=data.get("ocr_applied", False),
            pdf_type=data.get("pdf_type", "NON_PDF"),
            parser_used=data.get("parser_used", "docling_fast"),
            ocr_decision=data.get("ocr_decision", "SKIPPED_TEXT_PRESENT"),
            stage_metrics=data.get("stage_metrics", {}),
        )


def _init_fast_converter() -> DocumentConverter:
    options = PdfPipelineOptions()
    options.do_ocr = False
    options.allow_external_plugins = True
    options.do_table_structure = settings.DOCUMENT_TABLE_STRUCTURE_ENABLED
    logger.info(f"[OCR_INIT] Fast converter: engine=docling_fast, do_ocr=False, allow_external_plugins=True")
    return DocumentConverter(format_options={"pdf": PdfFormatOption(pipeline_options=options)})


def _init_ocr_converter() -> DocumentConverter:
    options = PdfPipelineOptions()
    options.do_ocr = True
    options.do_table_structure = settings.DOCUMENT_TABLE_STRUCTURE_ENABLED
    options.allow_external_plugins = True
    options.ocr_options = PPOCRv6Options(force_full_page_ocr=True)
    logger.info(f"[OCR_INIT] OCR converter: engine={_OCR_ENGINE}, ocr=enabled, allow_external_plugins=True, force_full_page=True")
    return DocumentConverter(format_options={"pdf": PdfFormatOption(pipeline_options=options)})


_fast_converter_instance: DocumentConverter | None = None
_ocr_converter_instance: DocumentConverter | None = None
_converter_lock = Lock()
_parser_thread_pool = ThreadPoolExecutor(max_workers=max(1, settings.DOCUMENT_PARSER_WORKERS), thread_name_prefix="docling_parser")


def _get_fast_converter() -> DocumentConverter:
    global _fast_converter_instance
    if _fast_converter_instance is None:
        with _converter_lock:
            if _fast_converter_instance is None:
                _fast_converter_instance = _init_fast_converter()
    return _fast_converter_instance


def _get_ocr_converter() -> DocumentConverter:
    global _ocr_converter_instance
    if _ocr_converter_instance is None:
        with _converter_lock:
            if _ocr_converter_instance is None:
                _ocr_converter_instance = _init_ocr_converter()
    return _ocr_converter_instance


def _classify_pdf(content: bytes) -> tuple[str, str, int, bool]:
    try:
        import fitz

        document = fitz.open(stream=content, filetype="pdf")
        try:
            native_text = "\n".join(page.get_text("text", sort=True) for page in document).strip()
            native_char_count = len(native_text)
            has_images = any(page.get_images() for page in document)
        finally:
            document.close()
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


def _extract_native_docx(content: bytes) -> str:
    try:
        import docx
        from docx.oxml.table import CT_Tbl
        from docx.oxml.text.paragraph import CT_P
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        document = docx.Document(BytesIO(content))
        lines: list[str] = []
        for block in document.element.body:
            if isinstance(block, CT_P):
                paragraph = Paragraph(block, document)
                text = paragraph.text.strip()
                if text:
                    is_heading = paragraph.style and paragraph.style.name and paragraph.style.name.startswith("Heading")
                    lines.append(f"## {text}" if is_heading else text)
            elif isinstance(block, CT_Tbl):
                table = Table(block, document)
                for index, row in enumerate(table.rows):
                    cells = [cell.text.replace("\n", " ").strip() for cell in row.cells]
                    if any(cells):
                        lines.append("| " + " | ".join(cells) + " |")
                        if index == 0:
                            lines.append("|" + "|".join(["---"] * len(cells)) + "|")
        return "\n\n".join(lines).strip()
    except Exception as exc:
        logger.warning(f"python-docx native extraction failed: {exc}")
        return ""


def _get_pdf_page_count(content: bytes) -> int:
    try:
        import fitz

        document = fitz.open(stream=content, filetype="pdf")
        try:
            return max(1, document.page_count)
        finally:
            document.close()
    except Exception:
        return 1


class DocumentConversionService:
    @classmethod
    def generate(cls, filename: str, content: bytes) -> MarkdownResult:
        normalized = UploadService.normalize_filename(filename)
        UploadService.validate_content(normalized.safe_filename, content)
        filename = normalized.safe_filename
        extension = normalized.extension
        logger.info(f"Starting document conversion for '{filename}' ({len(content)} bytes)...")

        pdf_type = "NON_PDF"
        native_text = ""
        native_char_count = 0
        has_images = False
        if extension == "pdf":
            pdf_type, native_text, native_char_count, has_images = _classify_pdf(content)
        elif extension == "docx":
            native_text = _extract_native_docx(content)
            native_char_count = len(native_text)

        logger.info(f"[STAGE 1: NATIVE EXTRACTION] '{filename}': type={pdf_type}, chars={native_char_count}, images={has_images}")
        use_native_text = settings.PREFER_NATIVE_TEXT_EXTRACTION and native_char_count >= settings.AUTO_OCR_MIN_TEXT_CHARS
        if use_native_text:
            fast_text, fast_duration_ms, docling_document = native_text, 0.0, None
        else:
            fast_text, fast_duration_ms, docling_document = cls._convert_fast(filename, content)
        fast_length = len(fast_text)
        ocr_decision = cls._ocr_decision(extension, pdf_type, fast_length, native_char_count)
        ocr_text = ""
        ocr_duration_ms = 0.0
        ocr_applied = False

        if ocr_decision == "INVOKED_SPARSE_TEXT":
            ocr_text, ocr_duration_ms, ocr_document = cls._convert_ocr(filename, content)
            ocr_applied = ocr_document is not None
            if ocr_document and len(ocr_text) > fast_length:
                docling_document = ocr_document

        parser_used = f"native_{extension}" if use_native_text else "docling_fast"
        raw_text = fast_text
        if ocr_applied and len(ocr_text) > max(fast_length, native_char_count):
            raw_text, parser_used = ocr_text, "docling_ocr"
        elif fast_length < settings.AUTO_OCR_MIN_TEXT_CHARS:
            raw_text, parser_used = native_text, f"native_{extension}"

        raw_text = cls._recover_structured_headings(raw_text, docling_document)
        clean_text = ResumeTextNormalizer.sanitize(raw_text)
        if not clean_text or (len(clean_text) < 20 and "<!-- image -->" in raw_text):
            raise ValueError(f"No readable text or content could be extracted from CV document '{filename}'.")

        page_count = len(docling_document.pages) if docling_document and getattr(docling_document, "pages", None) else _get_pdf_page_count(content) if extension == "pdf" else 1
        is_scanned = pdf_type == "SCANNED_PDF" or (
            extension == "pdf" and ("<!-- image -->" in raw_text or (ocr_applied and native_char_count < 50) or bool(docling_document and getattr(docling_document, "pictures", None)))
        )
        metrics = {
            "pdf_type": pdf_type,
            "native_char_count": native_char_count,
            "has_images": has_images,
            "fast_docling_chars": fast_length,
            "fast_docling_ms": fast_duration_ms,
            "ocr_decision": ocr_decision,
            "ocr_engine": _OCR_ENGINE if ocr_applied else "none",
            "ocr_chars": len(ocr_text),
            "ocr_ms": ocr_duration_ms,
            "final_char_count": len(clean_text),
            "parser_used": parser_used,
        }
        # Content-loss detection: warn if final extraction is significantly shorter than native text.
        # This can indicate OCR/Docling failed to recover content from a hybrid/scanned PDF.
        content_loss_detected = False
        if native_char_count > 200 and len(clean_text) < native_char_count * 0.5:
            content_loss_detected = True
            logger.warning(
                f"[CONTENT_LOSS] '{filename}': final_chars={len(clean_text)} is <50% of native_chars={native_char_count}. "
                f"parser={parser_used}, pdf_type={pdf_type}, ocr_applied={ocr_applied}. "
                "Check if Docling/OCR dropped content. Verify extraction is complete."
            )

        logger.info(
            f"[EXTRACTION_TELEMETRY] '{filename}': "
            f"native_chars={native_char_count} docling_chars={fast_length} "
            f"ocr_chars={len(ocr_text)} final_chars={len(clean_text)} "
            f"content_loss_detected={content_loss_detected} "
            f"parser={parser_used} pdf_type={pdf_type}"
        )
        logger.info(f"[STAGE 5: FINAL TEXT] '{filename}': type={pdf_type}, parser={parser_used}, ocr_engine={_OCR_ENGINE if ocr_applied else 'none'}, chars={len(clean_text)}")
        return MarkdownResult(
            markdown=clean_text,
            page_count=page_count,
            is_scanned=is_scanned,
            ocr_applied=ocr_applied,
            pdf_type=pdf_type,
            parser_used=parser_used,
            ocr_decision=ocr_decision,
            stage_metrics={
                **metrics,
                "content_loss_detected": content_loss_detected,
                "llm_chars": None,  # Set later by LLM prompt builder — not extraction concern
            },
        )

    @classmethod
    def generate_with_timeout(
        cls,
        filename: str,
        content: bytes,
        timeout_seconds: float | None = None,
    ) -> MarkdownResult:
        timeout = timeout_seconds if timeout_seconds is not None else settings.EXTRACTION_TIMEOUT_SECONDS
        future = _parser_thread_pool.submit(cls.generate, filename, content)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError as exc:
            logger.error(f"Extraction timed out after {timeout} seconds for '{filename}'.")
            raise TimeoutError(f"Extraction timed out after {timeout} seconds for '{filename}'.") from exc

    @staticmethod
    def _convert_fast(filename: str, content: bytes) -> tuple[str, float, Any]:
        started = time.perf_counter()
        try:
            result = _get_fast_converter().convert(DocumentStream(name=filename, stream=BytesIO(content)))
            document = result.document
            text = document.export_to_markdown().strip() if document else ""
            duration = round((time.perf_counter() - started) * 1000.0, 2)
            logger.info(f"[STAGE 2: DOCLING FAST] '{filename}': chars={len(text)}, duration={duration}ms")
            return text, duration, document
        except Exception as exc:
            duration = round((time.perf_counter() - started) * 1000.0, 2)
            logger.warning(f"[STAGE 2: DOCLING FAST] Error for '{filename}': {exc} ({duration}ms)")
            return "", duration, None

    @staticmethod
    def _convert_ocr(filename: str, content: bytes) -> tuple[str, float, Any]:
        started = time.perf_counter()
        try:
            logger.info(f"[STAGE 3: OCR START] '{filename}': engine={_OCR_ENGINE}, status=RUNNING")
            result = _get_ocr_converter().convert(DocumentStream(name=filename, stream=BytesIO(content)))
            document = result.document if result else None
            text = document.export_to_markdown().strip() if document else ""
            page_count = len(document.pages) if document and getattr(document, "pages", None) else 0
            duration = round((time.perf_counter() - started) * 1000.0, 2)
            logger.info(f"[STAGE 4: OCR DONE] '{filename}': engine={_OCR_ENGINE}, chars={len(text)}, pages={page_count}, duration={duration}ms")
            return text, duration, document
        except Exception as exc:
            duration = round((time.perf_counter() - started) * 1000.0, 2)
            logger.warning(f"[STAGE 4: OCR EXECUTION] '{filename}': engine={_OCR_ENGINE}, status=FAILED, error={exc}, fallback=native, duration={duration}ms")
            return "", duration, None

    @staticmethod
    def _ocr_decision(extension: str, pdf_type: str, fast_length: int, native_length: int) -> str:
        if extension != "pdf":
            decision = "SKIPPED_NON_PDF"
        elif pdf_type in ("TEXT_PDF", "HYBRID_PDF") and (fast_length >= 50 or native_length >= 50):
            decision = "SKIPPED_TEXT_PRESENT"
        elif fast_length >= settings.AUTO_OCR_MIN_TEXT_CHARS or native_length >= settings.AUTO_OCR_MIN_TEXT_CHARS:
            decision = "SKIPPED_SUFFICIENT_TEXT"
        else:
            decision = "INVOKED_SPARSE_TEXT"
        ocr_enabled = decision == "INVOKED_SPARSE_TEXT"
        logger.info(f"[OCR_DECISION] type={pdf_type}, fast_chars={fast_length}, native_chars={native_length}, decision={decision}, ocr_enabled={ocr_enabled}, engine={_OCR_ENGINE if ocr_enabled else 'none'}")
        return decision

    @staticmethod
    def _recover_structured_headings(raw_text: str, document: Any) -> str:
        structured = document.export_to_dict() if document and hasattr(document, "export_to_dict") else {}
        recovered: list[str] = []
        texts = structured.get("texts", [])
        for index, item in enumerate(texts):
            text = item.get("text", "").strip()
            if text and item.get("label") in ("title", "section_header") and text not in raw_text:
                recovered.append(text)
            elif text and item.get("content_layer") == "furniture" and text not in raw_text:
                previous_text = next(
                    (texts[previous].get("text", "").strip() for previous in range(index - 1, -1, -1) if texts[previous].get("text", "").strip() in raw_text),
                    "",
                )
                if previous_text:
                    before, separator, after = raw_text.rpartition(previous_text)
                    raw_text = f"{before}{separator}\n\n{text}{after}"
                else:
                    recovered.append(text)
        return "\n\n".join(recovered + [raw_text]) if recovered else raw_text


MarkdownGenerator = DocumentConversionService
