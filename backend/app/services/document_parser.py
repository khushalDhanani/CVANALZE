import re
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
        quality_metrics: dict[str, Any] | None = None,
        resume_json: dict[str, Any] | None = None,
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
        self.quality_metrics = quality_metrics or {}
        self.resume_json = resume_json or {}

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
            "quality_metrics": self.quality_metrics,
            "resume_json": self.resume_json,
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
            quality_metrics=data.get("quality_metrics", {}),
            resume_json=data.get("resume_json", {}),
        )


class TextSanitizer:
    @classmethod
    def sanitize(cls, raw_text: str) -> str:
        if not raw_text:
            return ""

        # 1. Remove HTML image placeholders and markdown comment artifacts
        text = re.sub(r"<!--\s*image\s*-->", "", raw_text)
        text = re.sub(r"<!--\s*.*?\s*-->", "", text, flags=re.DOTALL)

        # 2. Fix spaced-letter words and headings (e.g. "E D U C A T I O N", "W O R K   E X P E R I E N C E")
        def _fix_spaced_line(line: str) -> str:
            if not line.strip():
                return ""

            header_prefix = ""
            match_header = re.match(r"^(\s*#+\s*)(.*)$", line)
            if match_header:
                header_prefix = match_header.group(1)
                content = match_header.group(2)
            else:
                content = line

            parts = re.split(r"\s{2,}", content.strip())
            fixed_parts = []
            for part in parts:
                tokens = part.split()
                if len(tokens) >= 3 and all(len(t) == 1 for t in tokens):
                    fixed_parts.append("".join(tokens))
                elif len(tokens) >= 2 and all(len(t) == 1 for t in tokens) and len(part.replace(" ", "")) >= 3:
                    fixed_parts.append("".join(tokens))
                else:
                    fixed_parts.append(part)

            rejoined = " ".join(fixed_parts)
            return f"{header_prefix}{rejoined}" if header_prefix else rejoined

        lines = text.splitlines()
        cleaned_lines = []
        for line in lines:
            cleaned_line = _fix_spaced_line(line).rstrip()
            cleaned_lines.append(cleaned_line)

        text = "\n".join(cleaned_lines)

        # 3. Normalize common heading variations
        text = re.sub(r"##\s*WORK\s+EXPERIENCE", "## WORK EXPERIENCE", text, flags=re.IGNORECASE)
        text = re.sub(r"##\s*EDUCATION", "## EDUCATION", text, flags=re.IGNORECASE)
        text = re.sub(r"##\s*SKILLS", "## SKILLS", text, flags=re.IGNORECASE)
        text = re.sub(r"##\s*PROJECTS", "## PROJECTS", text, flags=re.IGNORECASE)
        text = re.sub(r"##\s*CONTACT", "## CONTACT", text, flags=re.IGNORECASE)

        # 4. Collapse consecutive empty lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


class QualityMetricsCalculator:
    @classmethod
    def compute(
        cls,
        text: str,
        page_count: int,
        pdf_type: str,
        parser_used: str,
        ocr_applied: bool,
    ) -> dict[str, Any]:
        clean_text = text.strip()
        char_count = len(clean_text)
        words = re.findall(r"\b[a-zA-Z0-9_+-]+\b", clean_text)
        word_count = len(words)

        section_patterns = {
            "contact": r"\b(contact|email|phone|address|linkedin|github|location)\b",
            "summary": r"\b(summary|profile|about|objective|overview)\b",
            "experience": r"\b(experience|employment|work history|career|work experience)\b",
            "education": r"\b(education|academic|qualification|university|degree|college)\b",
            "skills": r"\b(skills|technical skills|technologies|expertise|competencies)\b",
            "certifications": r"\b(certifications|certificates|licenses|courses)\b",
            "projects": r"\b(projects|key projects|personal projects)\b",
        }

        text_lower = clean_text.lower()
        sections_detected = []
        for sec_name, pattern in section_patterns.items():
            if re.search(pattern, text_lower):
                sections_detected.append(sec_name)

        core_sections = {"contact", "summary", "experience", "education", "skills"}
        detected_core = [s for s in sections_detected if s in core_sections]
        section_score = len(detected_core) * 0.10

        has_email = bool(re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", clean_text))
        has_phone = bool(re.search(r"(\+?\d{1,4}[\s.-]?)?\(?\d{3,5}\)?[\s.-]?\d{3,5}[\s.-]?\d{3,5}", clean_text))
        has_location = bool(re.search(r"\b[A-Z][a-zA-Z\s]+,\s*[A-Z][a-zA-Z\s]+\b", clean_text))
        contact_score = (0.10 if has_email else 0) + (0.10 if has_phone else 0) + (0.05 if has_location else 0)

        words_per_page = word_count / max(page_count, 1)
        if words_per_page >= 150:
            density_score = 0.25
        elif words_per_page >= 80:
            density_score = 0.20
        elif words_per_page >= 30:
            density_score = 0.10
        else:
            density_score = 0.05

        completeness_score = round(min(1.0, section_score + contact_score + density_score), 2)

        return {
            "pages": page_count,
            "characters": char_count,
            "words": word_count,
            "sections_detected": sections_detected,
            "sections_count": len(sections_detected),
            "completeness_score": completeness_score,
            "has_email": has_email,
            "has_phone": has_phone,
            "pdf_type": pdf_type,
            "parser_used": parser_used,
            "ocr_applied": ocr_applied,
        }


class ResumeJsonExtractor:
    @classmethod
    def extract(cls, text: str, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
        if not text:
            return {}

        text_lines = text.splitlines()

        email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        email = email_match.group(0) if email_match else None

        phone_match = re.search(r"(\+?\d{1,4}[\s.-]?)?\(?\d{3,5}\)?[\s.-]?\d{3,5}[\s.-]?\d{3,5}", text)
        phone = phone_match.group(0).strip() if phone_match else None

        linkedin_match = re.search(r"(linkedin\.com/in/[\w-]+)", text, re.IGNORECASE)
        linkedin = linkedin_match.group(0) if linkedin_match else None

        github_match = re.search(r"(github\.com/[\w-]+)", text, re.IGNORECASE)
        github = github_match.group(0) if github_match else None

        candidate_name = ""
        for line in text_lines[:10]:
            clean_l = line.strip()
            if not clean_l or clean_l.startswith("#") or "CONTACT" in clean_l.upper() or "@" in clean_l:
                continue
            cleaned_title = re.sub(
                r"\b(FULL STACK|DEVELOPER|ENGINEER|SR|SENIOR|MOBILE)\b.*$",
                "",
                clean_l,
                flags=re.IGNORECASE,
            ).strip()
            if len(cleaned_title) > 2 and len(cleaned_title) < 40:
                candidate_name = cleaned_title
                break
        if not candidate_name and text_lines:
            candidate_name = text_lines[0].replace("#", "").strip()

        location = None
        loc_match = re.search(r"\b([A-Z][a-zA-Z\s]+,\s*[A-Z][a-zA-Z\s]+)\b", text)
        if loc_match:
            location = loc_match.group(1).strip()

        contact_info = {
            "name": candidate_name,
            "email": email,
            "phone": phone,
            "location": location,
            "linkedin": linkedin,
            "github": github,
        }

        sections: dict[str, list[str]] = {}
        current_section = "general"
        sections[current_section] = []

        section_heading_re = re.compile(
            r"^(?:#+|\*\*)\s*(SUMMARY|PROFILE SUMMARY|PROFILE|WORK EXPERIENCE|EXPERIENCE|EMPLOYMENT|EDUCATION|SKILLS|TECHNICAL SKILLS|PROJECTS|CERTIFICATIONS|LANGUAGES|HOBBIES|CONTACT)\b",
            re.IGNORECASE,
        )

        for line in text_lines:
            m = section_heading_re.match(line.strip())
            if m:
                heading = m.group(1).upper()
                if "EXPERIENCE" in heading or "EMPLOYMENT" in heading:
                    current_section = "experience"
                elif "EDUCATION" in heading:
                    current_section = "education"
                elif "SKILL" in heading:
                    current_section = "skills"
                elif "PROJECT" in heading:
                    current_section = "projects"
                elif "SUMMARY" in heading or "PROFILE" in heading:
                    current_section = "summary"
                elif "CERTIFICATION" in heading:
                    current_section = "certifications"
                else:
                    current_section = heading.lower()

                if current_section not in sections:
                    sections[current_section] = []
            else:
                sections[current_section].append(line)

        summary_text = "\n".join(sections.get("summary", [])).strip()

        work_experience = []
        exp_lines = sections.get("experience", [])
        current_job: dict[str, Any] = {}
        for line in exp_lines:
            clean_l = line.strip()
            if not clean_l:
                continue
            if clean_l.startswith("##") or clean_l.startswith("###") or re.search(r"\b(20\d{2}|19\d{2})\b", clean_l):
                if current_job.get("company") or current_job.get("job_title"):
                    work_experience.append(current_job)
                    current_job = {}
                if clean_l.startswith("#"):
                    current_job["company"] = clean_l.replace("#", "").strip()
                elif re.search(r"\b(20\d{2}|Present)\b", clean_l, re.IGNORECASE):
                    current_job["dates"] = clean_l
                else:
                    current_job["job_title"] = clean_l
            elif clean_l.startswith("-") or clean_l.startswith("•"):
                if "responsibilities" not in current_job:
                    current_job["responsibilities"] = []
                current_job["responsibilities"].append(clean_l.lstrip("-• ").strip())
            else:
                if "description" not in current_job:
                    current_job["description"] = clean_l
                else:
                    current_job["description"] += " " + clean_l
        if current_job.get("company") or current_job.get("job_title") or current_job.get("responsibilities"):
            work_experience.append(current_job)

        education = []
        edu_lines = sections.get("education", [])
        current_edu: dict[str, Any] = {}
        for line in edu_lines:
            clean_l = line.strip()
            if not clean_l:
                continue
            if clean_l.startswith("#"):
                if current_edu.get("institution") or current_edu.get("degree"):
                    education.append(current_edu)
                    current_edu = {}
                current_edu["institution"] = clean_l.replace("#", "").strip()
            elif "CPI" in clean_l or "GPA" in clean_l or "Grade" in clean_l:
                current_edu["grade"] = clean_l.lstrip("-• ").strip()
            elif re.search(r"\b(20\d{2}|19\d{2})\b", clean_l):
                current_edu["dates"] = clean_l
            elif "BTech" in clean_l or "Degree" in clean_l or "Bachelor" in clean_l or "Master" in clean_l or "Ph" in clean_l:
                current_edu["degree"] = clean_l.lstrip("-• ").strip()
            elif clean_l.startswith("-") or clean_l.startswith("•"):
                if "details" not in current_edu:
                    current_edu["details"] = []
                current_edu["details"].append(clean_l.lstrip("-• ").strip())

        if current_edu.get("institution") or current_edu.get("degree"):
            education.append(current_edu)

        skills_lines = sections.get("skills", [])
        categorized_skills: dict[str, list[str]] = {}
        all_skills: list[str] = []

        for line in skills_lines:
            clean_l = line.lstrip("-• ").strip()
            if not clean_l:
                continue
            if ":" in clean_l:
                category, items_str = clean_l.split(":", 1)
                cat_name = category.strip()
                items = [it.strip() for it in re.split(r"[,;&|]+", items_str) if it.strip()]
                categorized_skills[cat_name] = items
                all_skills.extend(items)
            else:
                items = [it.strip() for it in re.split(r"[,;&|]+", clean_l) if it.strip()]
                all_skills.extend(items)

        seen = set()
        dedup_skills = []
        for s in all_skills:
            if s.lower() not in seen:
                seen.add(s.lower())
                dedup_skills.append(s)

        projects = []
        proj_lines = sections.get("projects", [])
        current_proj: dict[str, Any] = {}

        for line in proj_lines:
            clean_l = line.strip()
            if not clean_l:
                continue
            if clean_l.startswith("##") or clean_l.startswith("###"):
                if current_proj.get("name"):
                    projects.append(current_proj)
                    current_proj = {}
                current_proj["name"] = clean_l.replace("#", "").strip()
            elif "|" in clean_l and not clean_l.startswith("-"):
                techs = [t.strip() for t in clean_l.split("|") if t.strip()]
                current_proj["technologies"] = techs
            elif clean_l.startswith("-") or clean_l.startswith("•"):
                if "bullet_points" not in current_proj:
                    current_proj["bullet_points"] = []
                current_proj["bullet_points"].append(clean_l.lstrip("-• ").strip())
            else:
                if "description" not in current_proj:
                    current_proj["description"] = clean_l
                else:
                    current_proj["description"] += " " + clean_l

        if current_proj.get("name"):
            projects.append(current_proj)

        certifications = [
            l.lstrip("-• ").strip() for l in sections.get("certifications", []) if l.strip()
        ]

        return {
            "contact_info": contact_info,
            "summary": summary_text,
            "work_experience": work_experience,
            "education": education,
            "skills": {
                "categorized": categorized_skills,
                "all_skills": dedup_skills,
            },
            "projects": projects,
            "certifications": certifications,
            "quality_metrics": metrics or {},
        }


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
    Inspect PDF using PyMuPDF (fitz) with layout sorting to detect native text,
    reading order, images, and classify document as TEXT_PDF, HYBRID_PDF, or SCANNED_PDF.
    Returns tuple: (pdf_type, native_text, native_char_count, has_images)
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=content, filetype="pdf")
        page_texts = [page.get_text("text", sort=True) for page in doc]
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

        # Stage 1: Detect PDF Type & Extract Native Selectable Text (layout sorted)
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
        raw_final_text = fast_markdown_text

        if ocr_applied and len(ocr_markdown_text) > len(raw_final_text):
            raw_final_text = ocr_markdown_text
            parser_used = "docling_ocr"

        if len(raw_final_text.strip()) < 20 and len(native_pdf_text.strip()) >= 20:
            logger.info(
                f"Using native PDF text ({len(native_pdf_text)} chars) for '{filename}' "
                f"as primary Docling output was empty or sparse."
            )
            raw_final_text = native_pdf_text
            parser_used = "native_fitz"

        # Sanitize text
        final_text_clean = TextSanitizer.sanitize(raw_final_text)

        if not final_text_clean or (len(final_text_clean) < 20 and "<!-- image -->" in raw_final_text):
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
            "<!-- image -->" in raw_final_text
            or (ocr_applied and native_char_count < 50)
            or (docling_doc and hasattr(docling_doc, "pictures") and len(docling_doc.pictures) > 0)
        ))

        # Compute Extraction Quality Metrics
        quality_metrics = QualityMetricsCalculator.compute(
            text=final_text_clean,
            page_count=pages_count,
            pdf_type=pdf_type,
            parser_used=parser_used,
            ocr_applied=ocr_applied,
        )

        # Extract Structured Resume JSON
        resume_json = ResumeJsonExtractor.extract(final_text_clean, quality_metrics)

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
            "quality_metrics": quality_metrics,
        }

        logger.info(
            f"[STAGE 5: RESUME JSON] Successful extraction for '{filename}': "
            f"type={pdf_type}, parser={parser_used}, final_chars={len(final_text_clean)}, "
            f"words={quality_metrics['words']}, score={quality_metrics['completeness_score']}, "
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
            quality_metrics=quality_metrics,
            resume_json=resume_json,
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
