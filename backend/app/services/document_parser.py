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


class TextSanitizer:
    @classmethod
    def sanitize(cls, raw_text: str) -> str:
        if not raw_text:
            return ""

        # 1. Remove HTML image placeholders and markdown comment artifacts
        text = re.sub(r"<!--\s*image\s*-->", "", raw_text)
        text = re.sub(r"<!--\s*.*?\s*-->", "", text, flags=re.DOTALL)

        # 1.5 Remove markdown checkboxes hallucinated by Docling
        text = re.sub(r"-\s*\[[x\s]\]\s*", "", text, flags=re.IGNORECASE)

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

        # 3.5 Remove consecutive duplicate headings
        lines = text.splitlines()
        dedup_lines = []
        last_heading = None
        for line in lines:
            clean_l = line.strip()
            if clean_l.startswith("## "):
                heading_text = clean_l.lower()
                if heading_text == last_heading:
                    continue
                last_heading = heading_text
            elif clean_l:
                last_heading = None
            dedup_lines.append(line)
        text = "\n".join(dedup_lines)

        # 4. Flatten Markdown Tables
        def _flatten_table_line(l: str) -> str:
            if re.match(r"^\|[-\s\|]+\|$", l.strip()):
                return ""
            if l.strip().startswith("|") and l.strip().endswith("|"):
                parts = [p.strip() for p in l.split("|") if p.strip()]
                return "  ".join(parts)
            return l
            
        lines = [_flatten_table_line(l) for l in text.splitlines()]
        text = "\n".join(l for l in lines if l.strip())

        # 5. Collapse consecutive empty lines
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
    JOB_TITLE_KEYWORDS: set[str] = {
        "IT", "EXECUTIVE", "DEVELOPER", "ENGINEER", "MANAGER", "LEAD", "ANALYST", "SPECIALIST",
        "CONSULTANT", "ARCHITECT", "OFFICER", "DIRECTOR", "ADMINISTRATOR", "COORDINATOR", "TECHNICIAN",
        "ASSISTANT", "INTERN", "DESIGNER", "TESTER", "ACCOUNTANT", "SECRETARY", "REPRESENTATIVE",
        "OPERATOR", "SUPERVISOR", "HEAD", "CHIEF", "SENIOR", "JUNIOR", "ASSOCIATE", "PRINCIPAL",
        "STAFF", "FULL STACK", "FRONTEND", "BACKEND", "MOBILE", "DEVOPS", "CLOUD", "SOFTWARE",
        "SYSTEM", "NETWORK", "PROJECT", "PRODUCT", "SALES", "MARKETING", "FINANCE", "HR",
        "RECRUITER", "OPERATIONS", "GENERAL MANAGER", "CHEMIST", "PLANT", "SOLUTIONS", "DATA",
        "SCIENTIST", "SCRUM", "MASTER", "VP", "VICE", "PRESIDENT", "CEO", "CTO", "CFO", "COO",
        "FOUNDER", "CO-FOUNDER", "STUDENT", "FREELANCER", "TRAINEE", "RECEPTIONIST", "CLERK",
        "ADVISOR", "AUDITOR", "STRATEGIST"
    }

    RESUME_HEADER_KEYWORDS: set[str] = {
        "CURRICULUM", "VITAE", "RESUME", "CV", "BIODATA", "PROFILE", "SUMMARY", "CAREER",
        "OBJECTIVE", "EXPERIENCE", "EDUCATION", "SKILLS", "PROJECTS", "CERTIFICATIONS",
        "LANGUAGES", "REFERENCES", "DECLARATION", "PERSONAL", "DETAILS", "CONTACT",
        "INFORMATION", "ADDRESS", "PHONE", "EMAIL", "PAGE", "PVT", "LTD", "LLC", "INC",
        "INDUSTRIES", "COMPANY", "UNIVERSITY", "COLLEGE", "INSTITUTE", "SCHOOL", "BACHELOR",
        "MASTER", "DIPLOMA", "DEGREE", "WORK", "EMPLOYMENT", "TECHNICAL", "HOBBIES", "ACHIEVEMENTS"
    }

    @classmethod
    def extract_candidate_name(
        cls,
        text_lines: list[str],
        email: str | None,
        phone: str | None,
        location: str | None,
        filename: str | None = None,
    ) -> tuple[str, float, str, str]:
        """
        Deterministically extract and validate the candidate's real name.
        Returns: (candidate_name, confidence_score, confidence_level, extraction_source)
        """
        email_tokens: list[str] = []
        if email:
            local_part = email.split("@")[0].lower()
            clean_local = re.sub(r"\d+", "", local_part)
            raw_tokens = re.split(r"[._\-\s]+", clean_local)
            email_tokens = [t for t in raw_tokens if len(t) >= 2]

        def clean_line_text(l: str) -> str:
            clean = l.strip().lstrip("#*->•: ").rstrip(" *#:")
            if re.match(r"^name\s*[:-]?\s*", clean, re.IGNORECASE):
                clean = re.sub(r"^name\s*[:-]?\s*", "", clean, flags=re.IGNORECASE).strip()
            return clean

        def is_valid_name_candidate(candidate_str: str) -> bool:
            if not candidate_str or len(candidate_str) < 2 or len(candidate_str) > 45:
                return False
            if re.search(r"\d", candidate_str):
                return False
            if any(sym in candidate_str for sym in ["@", "http", "www.", ".com", ".org", ".io", "github", "linkedin"]):
                return False

            tokens = [t for t in re.split(r"\s+", candidate_str) if t]
            if not (1 <= len(tokens) <= 4):
                return False

            upper_tokens = [t.upper() for t in tokens]
            
            # Reject if ALL tokens or ANY 1-token line matches job titles or header keywords
            if len(tokens) == 1 and (upper_tokens[0] in cls.JOB_TITLE_KEYWORDS or upper_tokens[0] in cls.RESUME_HEADER_KEYWORDS):
                return False
            
            job_match_count = sum(1 for t in upper_tokens if t in cls.JOB_TITLE_KEYWORDS)
            header_match_count = sum(1 for t in upper_tokens if t in cls.RESUME_HEADER_KEYWORDS)

            if (job_match_count + header_match_count) >= len(tokens) * 0.5:
                return False

            if phone and (candidate_str in phone or phone in candidate_str):
                return False
            if email and (candidate_str in email or email in candidate_str):
                return False
            if location and (candidate_str in location or location in candidate_str):
                return False

            return True

        contact_line_idx = -1
        for i, line in enumerate(text_lines):
            if (email and email in line) or (phone and phone in line):
                contact_line_idx = i
                break

        search_indices: list[int] = []
        if contact_line_idx != -1:
            start_idx = max(0, contact_line_idx - 5)
            end_idx = min(len(text_lines), contact_line_idx + 6)
            search_indices.extend(list(range(start_idx, end_idx)))

        for i in range(min(10, len(text_lines))):
            if i not in search_indices:
                search_indices.append(i)

        header_candidates: list[tuple[str, bool]] = []
        for idx in search_indices:
            if idx >= len(text_lines):
                continue
            line = text_lines[idx]
            clean_l = clean_line_text(line)
            if not clean_l or "@" in clean_l or "CONTACT" in clean_l.upper():
                continue

            if is_valid_name_candidate(clean_l):
                name_words = [w.lower() for w in clean_l.split()]
                has_email_token_match = any(w in email_tokens for w in name_words) if email_tokens else False
                header_candidates.append((clean_l, has_email_token_match))

        for cand_name, has_email_match in header_candidates:
            if has_email_match:
                return (cand_name, 0.95, "HIGH", "header_email_validated")

        if header_candidates:
            cand_name, _ = header_candidates[0]
            return (cand_name, 0.85, "HIGH", "header_contact_section")

        if email_tokens:
            formatted_tokens = [t.capitalize() for t in email_tokens]
            email_derived_name = " ".join(formatted_tokens)
            if is_valid_name_candidate(email_derived_name):
                return (email_derived_name, 0.60, "MEDIUM", "email_username_fallback")

        if filename:
            clean_fn = re.sub(r"\.(pdf|docx|doc|txt)$", "", filename, flags=re.IGNORECASE)
            clean_fn = re.sub(r"[-_](cv|resume|updated|\d+)", "", clean_fn, flags=re.IGNORECASE)
            clean_fn = re.sub(r"[-_]+", " ", clean_fn).strip()
            if clean_fn:
                fn_derived_name = " ".join([w.capitalize() for w in clean_fn.split()])
                if is_valid_name_candidate(fn_derived_name):
                    return (fn_derived_name, 0.30, "LOW", "filename_fallback")

        return ("Unknown Candidate", 0.0, "FALLBACK", "default")

    @classmethod
    def extract(
        cls,
        text: str,
        metrics: dict[str, Any] | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
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

        location = None
        loc_match = re.search(r"\b([A-Z][a-zA-Z\s]+,\s*[A-Z][a-zA-Z\s]+)\b", text)
        if loc_match:
            location = loc_match.group(1).strip()

        candidate_name, name_conf, conf_level, name_source = cls.extract_candidate_name(
            text_lines=text_lines,
            email=email,
            phone=phone,
            location=location,
            filename=filename,
        )

        logger.info(
            f"[NAME_EXTRACTION] Extracted '{candidate_name}' "
            f"(confidence={name_conf:.2f}, level='{conf_level}', source='{name_source}')"
        )

        field_confidence = {
            "name": name_conf,
            "email": 1.0 if email else 0.0,
            "phone": 1.0 if phone else 0.0,
            "location": 1.0 if location else 0.0,
        }

        contact_info = {
            "name": candidate_name,
            "full_name": candidate_name,
            "candidate_name": candidate_name,
            "email": email,
            "phone": phone,
            "location": location,
            "linkedin": linkedin,
            "github": github,
            "field_confidence": field_confidence,
            "name_confidence": name_conf,
            "name_confidence_level": conf_level,
            "extraction_source": name_source,
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
                
            is_date_match = re.search(r"\b(20\d{2}|19\d{2})\b", clean_l)
            is_degree = any(d in clean_l for d in ["BTech", "Degree", "Bachelor", "Master", "Ph", "BE", "B.E.", "Diploma"])
            
            # If we see a new header or a new degree and we already have data, commit current_edu
            if clean_l.startswith("#") or (is_degree and current_edu.get("degree")):
                if current_edu.get("institution") or current_edu.get("degree"):
                    education.append(current_edu)
                    current_edu = {}
                    
            if clean_l.startswith("#"):
                current_edu["institution"] = clean_l.replace("#", "").strip()
            elif "CPI" in clean_l or "GPA" in clean_l or "Grade" in clean_l or "CPGA" in clean_l:
                current_edu["grade"] = clean_l.lstrip("-• ").strip()
            elif is_degree:
                current_edu["degree"] = clean_l.lstrip("-• ").strip()
                if is_date_match:
                    current_edu["dates"] = is_date_match.group(0)
            elif is_date_match:
                current_edu["dates"] = clean_l
            elif clean_l.startswith("-") or clean_l.startswith("•"):
                if "details" not in current_edu:
                    current_edu["details"] = []
                current_edu["details"].append(clean_l.lstrip("-• ").strip())
            else:
                if not current_edu.get("institution"):
                    current_edu["institution"] = clean_l

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


class MarkdownGenerator:
    @classmethod
    def generate(cls, filename: str, content: bytes) -> MarkdownResult:
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
            f"Starting MarkdownGenerator extraction pipeline for '{filename}' ({len(content)} bytes)..."
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

        structured_dict = docling_doc.export_to_dict() if docling_doc and hasattr(docling_doc, "export_to_dict") else {}

        # Recover missing text (headers hidden in pictures, and furniture elements)
        recovered_prepend = []
        if structured_dict and "texts" in structured_dict:
            texts_list = structured_dict["texts"]
            for i, item in enumerate(texts_list):
                item_text = item.get("text", "").strip()
                if not item_text:
                    continue
                label = item.get("label", "")
                content_layer = item.get("content_layer", "")
                
                # Recover titles/section headers not found in the raw markdown
                if label in ("title", "section_header") and item_text not in raw_final_text:
                    recovered_prepend.append(item_text)
                # Recover furniture (e.g. dates misclassified as headers/footers)
                elif content_layer == "furniture" and item_text not in raw_final_text:
                    prev_text = ""
                    for j in range(i - 1, -1, -1):
                        prev = texts_list[j].get("text", "").strip()
                        if prev and prev in raw_final_text:
                            prev_text = prev
                            break
                    if prev_text:
                        # Replace the LAST occurrence of prev_text to inject in proper reading order
                        parts = raw_final_text.rsplit(prev_text, 1)
                        if len(parts) == 2:
                            raw_final_text = parts[0] + prev_text + "\n\n" + item_text + parts[1]
                        else:
                            recovered_prepend.append(item_text)
                    else:
                        recovered_prepend.append(item_text)

        if recovered_prepend:
            raw_final_text = "\n\n".join(recovered_prepend) + "\n\n" + raw_final_text

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
            f"[STAGE 5: FINAL TEXT] Successful markdown extraction for '{filename}': "
            f"type={pdf_type}, parser={parser_used}, final_chars={len(final_text_clean)}, "
            f"pages={pages_count}, scanned={is_scanned}, ocr={ocr_applied}."
        )

        return MarkdownResult(
            markdown=final_text_clean,
            page_count=pages_count,
            is_scanned=is_scanned,
            ocr_applied=ocr_applied,
            pdf_type=pdf_type,
            parser_used=parser_used,
            ocr_decision=ocr_decision,
            stage_metrics=stage_metrics,
        )

    @classmethod
    def generate_with_timeout(
        cls,
        filename: str,
        content: bytes,
        timeout_seconds: float | None = None,
    ) -> MarkdownResult:
        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.EXTRACTION_TIMEOUT_SECONDS
        )

        future = _parser_thread_pool.submit(cls.generate, filename, content)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError as exc:
            logger.error(
                f"Extraction timed out after {timeout} seconds for '{filename}'."
            )
            raise TimeoutError(
                f"Extraction timed out after {timeout} seconds for '{filename}'."
            ) from exc
