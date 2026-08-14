from __future__ import annotations
import re
from typing import Any

from app.core.logging import logger
from app.core.rule_config_manager import RuleConfigManager
from app.services.dynamic_geo_heading_service import DynamicGeoAndHeadingService
from app.services.resume_normalizer import ResumeNormalizer



# Field-label tokens that should never be treated as a job title.
# CVs formatted like "Duration: July 2021" or "Designation: Fitter" use
# these words as section labels — not as role titles.
_LABEL_PREFIX_DENYLIST: frozenset[str] = frozenset({
    "duration", "period", "tenure", "date", "from", "to",
    "organization", "company", "employer", "institution",
    "designation", "position", "role", "department",
    "location", "address", "place", "city",
    "qualification", "education", "degree", "board", "institute",
})
_NON_NAME_FIELD_LABELS: frozenset[str] = frozenset({
    "subject", "contact", "phone", "mobile", "email", "language", "address",
    "gender", "state", "nationality", "marital status", "date of birth", "dob",
    "pin", "pin code", "pincode", "personal data", "personal details", "resume", "cv",
})


class classproperty:
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        return self.func(owner)


class ResumeFieldExtractor:
    _SECTION_HEADING = re.compile(
        r"^(?:#+|\*\*|[-•*]|\d+\.?)?\s*(SUMMARY|PROFILE\s+SUMMARY|PROFESSIONAL\s+SUMMARY|EXECUTIVE\s+SUMMARY|CAREER\s+OBJECTIVE|OBJECTIVE|PROFILE|WORK\s+EXPERIENCE|WORKING\s+EXPERIENCE|PROFESSIONAL\s+EXPERIENCE|PRACTICAL\s+EXPOSURE|EXPERIENCE\s+SUMMARY|EMPLOYMENT\s+HISTORY|CAREER\s+HISTORY|WORK\s+HISTORY|PROFESSIONAL\s+BACKGROUND|EXPERIENCE\s+HIGHLIGHTS|RELEVANT\s+EXPERIENCE|PROJECTS?\s*&\s*EXPERIENCE|EXPERIENCE|EMPLOYMENT|EDUCATION|ACADEMIC\s+BACKGROUND|ACADEMICS|SKILLS|TECHNICAL\s+SKILLS|CORE\s+COMPETENCIES|KEY\s+SKILLS|PROJECTS|PROJECT\s+WORK|CERTIFICATIONS|CERTIFICATES|LANGUAGES|HOBBIES|CONTACT|PERSONAL\s+DETAILS)\b",
        re.IGNORECASE,
    )
    _DATE_PART = (
        r"(?:"
        r"(?:\d{1,2}(?:st|nd|rd|th)?\s+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?[,\s]+"
        r"(?:19|20)\d{2}"
        r"|(?:0?[1-9]|[12]\d|3[01])[/\.\-](?:0?[1-9]|1[0-2])[/\.\-](?:19|20)\d{2}"
        r"|"
        r"(?:0?[1-9]|1[0-2])[/\.\-](?:19|20)\d{2}"
        r"|(?:19|20)\d{2}[/\.\-](?:0?[1-9]|1[0-2])"
        r"|(?:Q[1-4]|Summer|Winter|Spring|Fall)\s+(?:19|20)\d{2}"
        r"|(?:19|20)\d{2}"
        r")"
    )
    _END_PART = (
        r"(?:"
        + _DATE_PART
        + r"|\b\d{2}\b"
        + r"|\b(?:present|current|continue|continuing|ongoing|now|till date|to date|onwards|till now|currently|presently|in progress|active)\b"
        r")"
    )
    _DATE_RANGE = re.compile(
        r"(?:\b|_|\()"
        + _DATE_PART
        + r"\s*(?:[\-–—~/]|->|\bto\b|\btill\b|\buntil\b|\bthrough\b)\s*"
        + _END_PART
        + r"(?:\b|_|\))",
        re.IGNORECASE,
    )
    _INLINE_NAME_LABEL = re.compile(r"\bname\s*[.:-]+\s*", re.IGNORECASE)
    _INLINE_NAME_OWNER = re.compile(
        r"\b(?:father'?s?|mother'?s?|spouse'?s?|company|organization|employer|institution|school|college)\s+$",
        re.IGNORECASE,
    )
    _INLINE_FIELD_BOUNDARY = re.compile(
        r"\s+(?:(?:permanent|current|postal|residential)\s+)?(?:address|date\s+of\s+birth|dob|contact(?:\s+no)?|phone|mobile|email|nationality|marital\s+status|gender|languages?\s+known)\s*[.:-]+",
        re.IGNORECASE,
    )

    @classproperty
    def JOB_TITLE_KEYWORDS(cls) -> set[str]:
        return RuleConfigManager.get_upper_keywords("job_title", "keywords")

    @classproperty
    def RESUME_HEADER_KEYWORDS(cls) -> set[str]:
        return DynamicGeoAndHeadingService.get_name_denylist()

    @classproperty
    def KNOWN_GAZETTEER(cls) -> set[str]:
        return DynamicGeoAndHeadingService.get_gazetteer_cities()

    @classproperty
    def LOCATION_BLACKLIST_KEYWORDS(cls) -> set[str]:
        return RuleConfigManager.get_keywords("location", "blacklist")

    @classproperty
    def NARRATIVE_SENTENCE_STARTERS(cls) -> set[str]:
        return RuleConfigManager.get_keywords("job_title", "narrative_starters")

    @classproperty
    def NARRATIVE_PHRASES(cls) -> set[str]:
        return RuleConfigManager.get_keywords("job_title", "narrative_phrases")

    @classproperty
    def GENERIC_SECTION_HEADERS(cls) -> set[str]:
        return DynamicGeoAndHeadingService.get_section_headings()

    @classmethod
    def extract_candidate_name(
        cls,
        text_lines: list[str],
        email: str | None,
        phone: str | None,
        location: str | None,
        filename: str | None = None,
    ) -> tuple[str, float, str, str]:
        name_cfg = RuleConfigManager.get_field_config("name")
        scores = name_cfg.confidence_scoring
        email_tokens = cls._email_name_tokens(email)
        contact_index = next(
            (index for index, line in enumerate(text_lines) if (email and email in line) or (phone and phone in line)),
            -1,
        )
        indices = list(range(min(10, len(text_lines))))
        if contact_index >= 0:
            indices = (
                list(
                    range(
                        max(0, contact_index - 5),
                        min(len(text_lines), contact_index + 6),
                    )
                )
                + indices
            )

        candidates: list[tuple[str, bool, int]] = []
        seen_indices: set[int] = set()
        for index in indices:
            if index in seen_indices or index >= len(text_lines):
                continue
            seen_indices.add(index)
            labeled_candidate = cls._name_from_labeled_field(text_lines[index])
            if labeled_candidate and cls._is_valid_name(labeled_candidate, email, phone, location):
                words = [word.lower() for word in labeled_candidate.split()]
                matches_email = any(
                    word in email_tokens or any(word in token or token in word for token in email_tokens if len(token) >= 3 and len(word) >= 3)
                    for word in words
                )
                candidates.append((labeled_candidate, matches_email, cls._name_structure_score(labeled_candidate, index, text_lines) + 8))

            candidate = cls._clean_name_line(text_lines[index])
            if not candidate or "@" in candidate or "CONTACT" in candidate.upper():
                continue
            if cls._is_valid_name(candidate, email, phone, location):
                words = [word.lower() for word in candidate.split()]
                matches_email = any(
                    word in email_tokens or any(word in token or token in word for token in email_tokens if len(token) >= 3 and len(word) >= 3)
                    for word in words
                )
                candidates.append((candidate, matches_email, cls._name_structure_score(candidate, index, text_lines)))
            else:
                # PDF/OCR output commonly places the name and role on one visual line.
                title_boundary = cls._find_job_title_boundary(candidate)
                stripped = candidate[:title_boundary].strip(" -|:") if title_boundary is not None and len(candidate) <= 120 else candidate
                if stripped and stripped != candidate and cls._is_valid_name(stripped, email, phone, location):
                    words = [word.lower() for word in stripped.split()]
                    matches_email = any(
                        word in email_tokens or any(word in token or token in word for token in email_tokens if len(token) >= 3 and len(word) >= 3)
                        for word in words
                    )
                    candidates.append((stripped, matches_email, cls._name_structure_score(stripped, index, text_lines)))

            combined_header_name = cls._name_from_combined_header(candidate) if len(candidate) <= 120 else None
            if combined_header_name and cls._is_valid_name(combined_header_name, email, phone, location):
                words = [word.lower() for word in combined_header_name.split()]
                matches_email = any(
                    word in email_tokens or any(word in token or token in word for token in email_tokens if len(token) >= 3 and len(word) >= 3)
                    for word in words
                )
                candidates.append((combined_header_name, matches_email, cls._name_structure_score(combined_header_name, index, text_lines)))

        # If no valid candidates found in header, search full document for lines matching email tokens
        if not candidates and email_tokens:
            for index, raw_l in enumerate(text_lines):
                candidate = cls._clean_name_line(raw_l)
                if not candidate or "@" in candidate:
                    continue
                title_boundary = cls._find_job_title_boundary(candidate)
                cand_clean = candidate[:title_boundary].strip(" -|:") if title_boundary is not None else candidate
                words = [word.lower() for word in cand_clean.split()]
                matches_email = any(
                    word in email_tokens or any(word in token or token in word for token in email_tokens if len(token) >= 3 and len(word) >= 3)
                    for word in words
                )
                if matches_email and cls._is_valid_name(cand_clean, email, phone, location):
                    candidates.append((cand_clean, True, cls._name_structure_score(cand_clean, index, text_lines)))
                    break

        email_validated = [candidate for candidate in candidates if candidate[1]]
        if email_validated:
            candidate = max(email_validated, key=lambda item: item[2])[0]
            return (
                candidate,
                scores.get("header_email_validated", 0.95),
                "HIGH",
                "header_email_validated",
            )
        if candidates:
            candidate = max(candidates, key=lambda item: item[2])[0]
            return (
                candidate,
                scores.get("header_contact_section", 0.85),
                "HIGH",
                "header_contact_section",
            )

        email_name = " ".join(token.capitalize() for token in email_tokens)
        if email_name and cls._is_valid_name(email_name, email, phone, location):
            return (
                email_name,
                scores.get("email_username_fallback", 0.30),
                "LOW",
                "email_username_fallback",
            )

        filename_name = cls._name_from_filename(filename)
        if filename_name and cls._is_valid_name(filename_name, email, phone, location):
            return (
                filename_name,
                scores.get("filename_fallback", 0.30),
                "LOW",
                "filename_fallback",
            )
        return (
            "Unknown Candidate",
            scores.get("default_fallback", 0.0),
            "FALLBACK",
            "default",
        )

    @classmethod
    def revalidate_candidate_name(cls, result: dict[str, Any]) -> None:
        """Refresh a stale, missing, or structurally invalid name from the stored CV text."""
        resume_json = result.get("resume_json")
        contact = resume_json.get("contact_info") if isinstance(resume_json, dict) else None
        contact_info = contact if isinstance(contact, dict) else {}
        source = str(contact_info.get("extraction_source") or result.get("name_extraction_source") or "").lower()
        cv_text = result.get("markdown") or result.get("text") or ""

        try:
            current_confidence = float(contact_info.get("name_confidence") or result.get("name_confidence") or 0.0)
            current_name = str(
                contact_info.get("name")
                or contact_info.get("full_name")
                or result.get("full_name")
                or result.get("candidate_name")
                or ""
            ).strip()
            email = contact_info.get("email") or result.get("email")
            phone = contact_info.get("phone") or result.get("phone")
            location = contact_info.get("location") or result.get("location")
            fallback_source = source in {"email_username_fallback", "filename_fallback", "default"}
            current_name_is_valid = cls._is_valid_name(current_name, email, phone, location)
            if not cv_text or (not fallback_source and current_name_is_valid):
                return
            name, confidence, confidence_level, extraction_source = cls.extract_candidate_name(
                str(cv_text).splitlines(),
                email,
                phone,
                location,
                result.get("filename"),
            )
        except Exception as exc:
            logger.warning("[CANDIDATE_NAME] Name refresh skipped for %s: %s", result.get("id") or result.get("scan_id"), exc)
            return

        if (current_name_is_valid and confidence <= current_confidence) or not name or name == "Unknown Candidate":
            return

        for key in ("name", "full_name", "candidate_name"):
            contact_info[key] = name
        contact_info["name_confidence"] = confidence
        contact_info["name_confidence_level"] = confidence_level
        contact_info["extraction_source"] = extraction_source
        if isinstance(contact_info.get("field_confidence"), dict):
            contact_info["field_confidence"]["name"] = confidence
        if isinstance(contact_info.get("field_confidence_tiers"), dict):
            contact_info["field_confidence_tiers"]["name"] = confidence_level

        result["full_name"] = name
        result["candidate_name"] = name
        result["name_confidence"] = confidence
        result["name_confidence_tier"] = confidence_level
        result["name_extraction_source"] = extraction_source
        if isinstance(result.get("field_confidence"), dict):
            result["field_confidence"]["name"] = confidence
        if isinstance(result.get("field_confidence_tiers"), dict):
            result["field_confidence_tiers"]["name"] = confidence_level

    @classmethod
    def extract_location(
        cls,
        text_lines: list[str],
        email: str | None = None,
        phone: str | None = None,
    ) -> tuple[str | None, float]:
        if not text_lines:
            return None, 0.0
        location_cfg = RuleConfigManager.get_field_config("location")
        contact_indices = set(range(min(10, len(text_lines))))
        for index, line in enumerate(text_lines):
            if (email and email in line) or (phone and phone in line):
                contact_indices.update(range(max(0, index - 3), min(len(text_lines), index + 4)))

        best_location: str | None = None
        best_confidence = 0.0
        for index in sorted(contact_indices):
            line = text_lines[index].strip()
            if not line or "@" in line or "http" in line.lower():
                continue
            for match in re.findall(r"\b([A-Z][a-zA-Z\s]+,\s*[A-Z][a-zA-Z\s]+)\b", line):
                candidate = match.strip()
                tokens = [token.lower() for token in re.split(r"[,\s]+", candidate) if token]
                if any(token in cls.LOCATION_BLACKLIST_KEYWORDS for token in tokens):
                    continue
                blacklist = cls.LOCATION_BLACKLIST_KEYWORDS
                if blacklist and any(token in blacklist for token in tokens):
                    return None, 0.0
                gazetteer_match = candidate.lower() in cls.KNOWN_GAZETTEER or any(token in cls.KNOWN_GAZETTEER for token in tokens)
                confidence = location_cfg.confidence_scoring.get(
                    "gazetteer_match_score" if gazetteer_match else "contact_block_generic_score",
                    0.90 if gazetteer_match else 0.50,
                )
                if confidence > best_confidence:
                    best_location, best_confidence = candidate, confidence
        return best_location, best_confidence

    @classmethod
    def is_valid_job_title(cls, candidate: str) -> bool:
        config = RuleConfigManager.get_field_config("job_title")
        max_words = config.downstream_gates.max_word_count or 7
        max_chars = config.downstream_gates.max_char_length or 60
        if not candidate or len(candidate) < 2 or len(candidate) > max_chars or candidate.endswith(".") or candidate.count(",") > 2:
            return False
        # Reject bare label tokens (e.g. "Duration:", "Designation:", "Period")
        stripped_colon = candidate.rstrip(":").strip().lower()
        if stripped_colon in _LABEL_PREFIX_DENYLIST:
            return False
        title_without_dates = cls._DATE_RANGE.sub("", candidate).strip(" ()-|–—")
        tokens = [token.lower() for token in re.split(r"[\s/\-&()]+", title_without_dates) if token]
        if not (1 <= len(tokens) <= max_words) or tokens[0] in cls.NARRATIVE_SENTENCE_STARTERS:
            return False
        if any(phrase in title_without_dates.lower() for phrase in cls.NARRATIVE_PHRASES):
            return False
        
        # Job titles must require stronger deterministic evidence.
        keywords = cls.JOB_TITLE_KEYWORDS
        if not keywords:
            return False
            
        return any(token.upper() in keywords for token in tokens)

    @classmethod
    def is_valid_company_name(cls, candidate: str) -> bool:
        max_chars = RuleConfigManager.get_field_config("company_name").downstream_gates.max_char_length or 70
        clean_candidate = candidate.lower().strip(" #*-:•") if candidate else ""
        return 2 <= len(candidate or "") <= max_chars and clean_candidate not in cls.GENERIC_SECTION_HEADERS

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
        phone_match = re.search(r"(\+?\d{1,4}[\s.-]?)?\(?\d{3,5}\)?[\s.-]?\d{3,5}[\s.-]?\d{3,5}", text)
        email = email_match.group(0) if email_match else None
        phone = phone_match.group(0).strip() if phone_match else None
        location, location_confidence = cls.extract_location(text_lines, email, phone)
        name, name_confidence, confidence_level, name_source = cls.extract_candidate_name(text_lines, email, phone, location, filename)
        logger.info(f"[NAME_EXTRACTION] Extracted '{name}' (confidence={name_confidence:.2f}, level='{confidence_level}', source='{name_source}')")

        sections = cls._split_sections(text_lines)
        exp_lines = sections.get("experience", [])
        extracted_exp = cls._extract_employment(exp_lines)
        if not extracted_exp and sections.get("general"):
            gen_lines = sections.get("general", [])
            if any(cls._DATE_RANGE.search(line) for line in gen_lines):
                extracted_exp = cls._extract_employment(gen_lines)
        extracted_education = cls._extract_education(sections.get("education", []) or text_lines)
        cls._recover_orphan_employment_dates(text, extracted_exp, extracted_education)

        result = {
            "contact_info": {
                "name": name,
                "full_name": name,
                "candidate_name": name,
                "email": email,
                "phone": phone,
                "location": location,
                "linkedin": cls._first_match(r"linkedin\.com/in/[\w-]+", text),
                "github": cls._first_match(r"github\.com/[\w-]+", text),
                "field_confidence": {
                    "name": name_confidence,
                    "email": 1.0 if email else 0.0,
                    "phone": 1.0 if phone else 0.0,
                    "location": location_confidence,
                },
                "name_confidence": name_confidence,
                "name_confidence_level": confidence_level,
                "extraction_source": name_source,
            },
            "summary": "\n".join(sections.get("summary", [])).strip(),
            "work_experience": extracted_exp,
            "education": extracted_education,
            "skills": cls._extract_skills(sections.get("skills", [])),
            "projects": cls._extract_projects(sections.get("projects", [])),
            "certifications": [line.lstrip("-• ").strip() for line in sections.get("certifications", []) if line.strip()],
            "quality_metrics": metrics or {},
        }
        
        # Zero-skill recovery fallback
        if not result["skills"]["all_skills"]:
            result["skills"] = cls._recover_skills_from_context(result["work_experience"], result["projects"])

        result["normalized"] = ResumeNormalizer.normalize(result, text).model_dump(mode="json")
        return result

    @classmethod
    def _recover_orphan_employment_dates(
        cls,
        text: str,
        jobs: list[dict[str, Any]],
        education: list[dict[str, Any]],
    ) -> None:
        """Recover dates displaced by multi-column PDF reading order only when pairing is unambiguous."""
        undated_jobs = [job for job in jobs if not str(job.get("dates") or "").strip()]
        if not undated_jobs:
            return

        orphan_ranges = [match.group(0).strip(" ()") for match in cls._DATE_RANGE.finditer(text)]
        used_ranges = [
            str(item.get("dates") or "").strip()
            for item in [*jobs, *education]
            if str(item.get("dates") or "").strip()
        ]
        for used in used_ranges:
            used_normalized = re.sub(r"\s+", " ", used).lower()
            for index, candidate in enumerate(orphan_ranges):
                if re.sub(r"\s+", " ", candidate).lower() == used_normalized:
                    orphan_ranges.pop(index)
                    break

        if len(orphan_ranges) != len(undated_jobs):
            return

        for job, date_range in zip(undated_jobs, orphan_ranges, strict=True):
            job["dates"] = date_range
            job["date_extraction_source"] = "orphan_range_document_order"

    @classmethod
    def _split_sections(cls, lines: list[str]) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {"general": []}
        current = "general"
        for line in lines:
            stripped_line = line.strip()
            match = cls._SECTION_HEADING.match(stripped_line)
            if not match:
                sections.setdefault(current, []).append(line)
                continue
            heading = match.group(1).upper()
            if "EXPERIENCE" in heading or "EMPLOYMENT" in heading or "EXPOSURE" in heading or "CAREER" in heading or "WORK HISTORY" in heading:
                current = "experience"
            elif "EDUCATION" in heading or "ACADEMIC" in heading:
                current = "education"
            elif "SKILL" in heading or "COMPETENC" in heading:
                current = "skills"
            elif "PROJECT" in heading:
                current = "projects"
            elif "SUMMARY" in heading or "PROFILE" in heading or "OBJECTIVE" in heading:
                current = "summary"
            elif "CERTIFICATION" in heading or "CERTIFICATE" in heading:
                current = "certifications"
            else:
                current = heading.lower()
            sections.setdefault(current, [])
            inline_content = stripped_line[match.end():].strip().lstrip(":-–—").strip()
            if inline_content:
                sections[current].append(inline_content)
        return sections

    @staticmethod
    def _looks_like_company(text: str) -> bool:
        """Return True if text looks like a company name using dynamic config suffixes."""
        if not text:
            return False
        
        from app.core.rule_config_manager import RuleConfigManager
        try:
            suffixes = RuleConfigManager.get_keywords("company_name", "suffixes")
        except KeyError:
            suffixes = set()
            
        if not suffixes:
            return False
            
        pattern = r"\b(" + "|".join(re.escape(s) for s in suffixes) + r")\b"
        return bool(re.search(pattern, text, re.IGNORECASE))

    @classmethod
    def _looks_like_title(cls, text: str) -> bool:
        """Return True if text looks like a job title rather than a company name."""
        if not text:
            return False
        keywords = cls.JOB_TITLE_KEYWORDS
        if not keywords:
            return False
            
        return any(k.lower() in text.lower() for k in keywords)

    @classmethod
    def _fix_company_title_swap(cls, current: dict[str, Any]) -> None:
        """Detect and correct company↔title swap."""
        company = current.get("company") or ""
        title = current.get("job_title") or ""
        # Case 1: company field contains a job title, title field contains a company
        if company and title and cls._looks_like_title(company) and cls._looks_like_company(title):
            current["company"], current["job_title"] = title, company
        # Case 2: company field contains a job title and title is empty
        elif company and not title and cls._looks_like_title(company) and not cls._looks_like_company(company):
            current["job_title"] = company
            current["company"] = ""
        # Case 3: title field contains a company name and company is empty
        elif title and not company and cls._looks_like_company(title) and not cls._looks_like_title(title):
            current["company"] = title
            current["job_title"] = ""

    @classmethod
    def _extract_employment(cls, lines: list[str]) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        current: dict[str, Any] = {}

        def commit() -> None:
            nonlocal current
            has_dates = bool(current.get("dates"))
            has_title = bool(current.get("job_title"))
            has_company = bool(current.get("company"))
            has_resp = bool(current.get("responsibilities"))
            
            if has_dates or (has_title and has_company) or (has_title and has_resp):
                cls._fix_company_title_swap(current)
                jobs.append(current)
            current = {}

        def resolve_unresolved() -> None:
            if not current.get("unresolved_header"):
                return
            for line in current["unresolved_header"]:
                if not current.get("company") and cls._looks_like_company(line):
                    current["company"] = line
                elif not current.get("job_title") and cls.is_valid_job_title(line):
                    current["job_title"] = line
                else:
                    current.setdefault("responsibilities", []).append(line)
            current.pop("unresolved_header", None)

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            date_match = cls._DATE_RANGE.search(line)
            clean_line = line.lstrip("-• \uf0b7").strip()

            # Handle Markdown headings
            if line.startswith(("##", "###")):
                resolve_unresolved()
                commit()
                heading_text = line.replace("#", "").strip()
                if date_match:
                    current["dates"] = date_match.group(0).strip(" ()")
                    heading_text = cls._DATE_RANGE.sub("", heading_text).strip(" ()-|–—")
                comma_parts = [p.strip() for p in heading_text.split(",", 1) if p.strip()]
                if len(comma_parts) >= 2 and cls._looks_like_company(comma_parts[1]):
                    current["job_title"] = comma_parts[0]
                    current["company"] = comma_parts[1]
                elif cls._looks_like_title(heading_text) and not cls._looks_like_company(heading_text):
                    current["job_title"] = heading_text
                elif cls.is_valid_company_name(heading_text):
                    current["company"] = heading_text
                else:
                    current.setdefault("unresolved_header", []).append(heading_text)
                continue

            # Special structured tables
            if line.startswith("|") and line.endswith("|"):
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if len(cells) >= 4:
                    from app.services.date_interval_parser import DateIntervalParser
                    start_date, _ = DateIntervalParser.parse_date_point(cells[-2], is_end_date=False)
                    end_date, _ = DateIntervalParser.parse_date_point(cells[-1], is_end_date=True)
                    if start_date and (end_date or DateIntervalParser.is_present(cells[-1])):
                        resolve_unresolved()
                        commit()
                        current["job_title"] = cells[0] or "Position"
                        current["company"] = cells[1] or "Organization"
                        current["dates"] = f"{cells[-2]} - {cells[-1]}"
                    continue
                if len(cells) == 2:
                    d_match = cls._DATE_RANGE.search(cells[1])
                    if d_match and cells[0] and cells[0] != "---":
                        resolve_unresolved()
                        commit()
                        combined = cells[0]
                        keywords = cls.JOB_TITLE_KEYWORDS
                        if keywords:
                            pattern = r"\s+(?=(?:" + "|".join(re.escape(k) for k in keywords) + r")\b)"
                            split = re.split(pattern, combined, maxsplit=1, flags=re.IGNORECASE)
                        else:
                            split = [combined]
                        if len(split) == 2:
                            company, title = split[0].strip(" -|–—"), split[1].strip(" -|–—")
                        else:
                            company, title = combined, "Position"
                        current["company"] = company or "Organization"
                        current["job_title"] = title
                        current["dates"] = d_match.group(0).strip(" ()")
                    continue
            
            has_date_match = bool(date_match)
            _desig_prefix_re = re.compile(r"^(?:designation|job\s+title|role|position)\s*[:\-]+\s*", re.IGNORECASE)
            is_explicit_title = bool(_desig_prefix_re.match(clean_line))
            clean_val = _desig_prefix_re.sub("", clean_line).strip() if is_explicit_title else clean_line
            
            is_title = is_explicit_title or cls.is_valid_job_title(clean_val)
            is_strict_company = cls._looks_like_company(clean_val)
            is_greedy_company = is_strict_company or cls.is_valid_company_name(clean_val)
            is_bullet = line.startswith(("-", "•"))

            state_has_title = bool(current.get("job_title"))
            state_has_company = bool(current.get("company"))
            state_has_date = bool(current.get("dates"))
            state_has_resp = bool(current.get("responsibilities"))

            incoming_is_strong_boundary = False
            if not is_bullet:
                if has_date_match and state_has_date:
                    incoming_is_strong_boundary = True
                elif is_explicit_title and state_has_title:
                    incoming_is_strong_boundary = True
                elif is_strict_company and state_has_company and (state_has_resp or state_has_date):
                    incoming_is_strong_boundary = True
                elif is_title and state_has_title and (state_has_date or state_has_resp):
                    incoming_is_strong_boundary = True

            if incoming_is_strong_boundary:
                resolve_unresolved()
                commit()

            if is_bullet:
                duration_match = re.search(r"(?:duration|period|tenure)\s*[:\-]+\s*(.+)$", clean_line, re.IGNORECASE)
                if duration_match:
                    remainder = duration_match.group(1).strip()
                    d_match = cls._DATE_RANGE.search(remainder)
                    if d_match:
                        current["dates"] = d_match.group(0).strip(" ()")
                        pre_date = remainder[: remainder.index(d_match.group(0))].strip(", :-")
                        if pre_date and not current.get("job_title") and cls.is_valid_job_title(pre_date):
                            current["job_title"] = pre_date
                        continue
                        
                org_match = re.search(r"(?:organization|company|employer)\s*[:\-]+\s*(.+)$", clean_line, re.IGNORECASE)
                if org_match and org_match.group(1).strip():
                    current["company"] = org_match.group(1).strip()
                    continue
                    
                if is_explicit_title:
                    current["job_title"] = clean_val
                    continue
                    
                bullet_date = cls._DATE_RANGE.search(clean_line)
                if bullet_date:
                    remaining = cls._DATE_RANGE.sub("", clean_line).strip(" ()-|–—")
                    if not remaining or len(remaining) < 5:
                        if not current.get("dates"):
                            current["dates"] = bullet_date.group(0).strip(" ()")
                        continue
                        
                current.setdefault("responsibilities", []).append(clean_line)
            else:
                if has_date_match:
                    if not current.get("dates"):
                        current["dates"] = date_match.group(0).strip(" ()")
                    possible_header = cls._DATE_RANGE.sub("", clean_line).strip(" ()-|–—")
                    if possible_header:
                        title_company_match = re.match(r"(.+?)\s+at\s+(.+)$", possible_header, re.IGNORECASE)
                        if title_company_match:
                            possible_title = title_company_match.group(1).strip()
                            possible_company = title_company_match.group(2).strip()
                            if not current.get("company") and cls.is_valid_company_name(possible_company):
                                current["company"] = possible_company
                            if not current.get("job_title") and cls.is_valid_job_title(possible_title):
                                current["job_title"] = possible_title
                        else:
                            if cls._looks_like_company(possible_header) and not current.get("company"):
                                current["company"] = possible_header
                            elif cls.is_valid_job_title(possible_header) and not current.get("job_title"):
                                current["job_title"] = possible_header
                            elif not current.get("job_title") and not current.get("company"):
                                current.setdefault("unresolved_header", []).append(possible_header)
                else:
                    if is_explicit_title:
                        if not current.get("job_title"):
                            current["job_title"] = clean_val
                        else:
                            current.setdefault("responsibilities", []).append(clean_val)
                    elif is_title and not current.get("job_title"):
                        if is_strict_company and not current.get("company") and not cls._looks_like_title(clean_val):
                            current["company"] = clean_val
                        else:
                            current["job_title"] = clean_val
                    elif is_greedy_company and not current.get("company"):
                        current["company"] = clean_val
                    elif not current.get("company") and not current.get("job_title") and len(clean_line) < 70 and not current.get("dates"):
                        current.setdefault("unresolved_header", []).append(clean_line)
                    else:
                        current.setdefault("responsibilities", []).append(clean_line)

        resolve_unresolved()
        commit()
        return jobs

    @classmethod
    def _extract_education(cls, lines: list[str]) -> list[dict[str, Any]]:
        education: list[dict[str, Any]] = []
        current: dict[str, Any] = {}
        degree_pattern = re.compile(
            r"\b(B\.?\s*Tech|B\.?E\.?|B\.?Sc\.?|Bachelor|M\.?\s*Tech|M\.?Sc\.?|Master|MBA|Ph\.?D|Diploma|Degree)\b",
            re.IGNORECASE,
        )

        def commit() -> None:
            nonlocal current
            if current.get("institution") or current.get("degree"):
                education.append(current)
            current = {}

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            date_match = cls._DATE_RANGE.search(line) or re.search(r"\b(?:19|20)\d{2}\b", line)
            if line.startswith("#"):
                commit()
                current["institution"] = line.replace("#", "").strip()
            elif degree_pattern.search(line):
                if current.get("degree"):
                    commit()
                current["degree"] = line.lstrip("-• ").strip()
                if date_match:
                    current["dates"] = date_match.group(0)
            elif re.search(r"\b(CPI|GPA|CGPA|Grade)\b", line, re.IGNORECASE):
                current["grade"] = line.lstrip("-• ").strip()
            elif date_match:
                current["dates"] = line
            elif line.startswith(("-", "•")):
                current.setdefault("details", []).append(line.lstrip("-• ").strip())
            elif not current.get("institution"):
                current["institution"] = line
        commit()
        return education

    @staticmethod
    def _is_junk_skill(item: str) -> bool:
        """Return True if item is a junk entry that should not be treated as a skill."""
        stripped = item.strip()
        if not stripped or len(stripped) < 2:
            return True
        # Reject markdown headings
        if stripped.startswith("##"):
            return True
        # Reject items that are only dashes/punctuation/equals
        if re.fullmatch(r"[-–—=_.\s*#]+", stripped):
            return True
        # Reject items with 4+ consecutive dashes
        if re.search(r"-{4,}", stripped):
            return True
        # Reject long responsibility sentences (>80 chars)
        if len(stripped) > 80:
            return True
        # Reject items containing :- (structured bullet prefix)
        if ":-" in stripped:
            return True
        # Reject items starting with " (quote remnants)
        if stripped.startswith('"') and len(stripped) > 1:
            stripped = stripped.lstrip('"').strip()
            if not stripped:
                return True
        return False

    @classmethod
    def _extract_skills(cls, lines: list[str]) -> dict[str, Any]:
        categorized: dict[str, list[str]] = {}
        all_skills: list[str] = []
        date_only_pattern = re.compile(
            r"(?i)^(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*)?(?:19|20)\d{2}\s*(?:-|to|till|until|–|—)\s*(?:present|current|now|(?:19|20)\d{2})$"
        )
        for raw_line in lines:
            line = raw_line.lstrip("-• ").strip()
            if not line:
                continue
            if ":" in line:
                category, values = line.split(":", 1)
                items = [
                    item.strip().lstrip('"').strip() for item in re.split(r"[,;&|]+", values)
                    if item.strip() and not date_only_pattern.match(item.strip()) and not cls._DATE_RANGE.fullmatch(item.strip()) and not cls._is_junk_skill(item.strip())
                ]
                if items:
                    categorized[category.strip()] = items
            else:
                items = [
                    item.strip().lstrip('"').strip() for item in re.split(r"[,;&|]+", line)
                    if item.strip() and not date_only_pattern.match(item.strip()) and not cls._DATE_RANGE.fullmatch(item.strip()) and not cls._is_junk_skill(item.strip())
                ]
            all_skills.extend(items)
        deduplicated: list[str] = []
        seen: set[str] = set()
        for skill in all_skills:
            clean = skill.strip().lstrip('"').rstrip('"').strip()
            if not clean or cls._is_junk_skill(clean):
                continue
            if clean.lower() not in seen:
                seen.add(clean.lower())
                deduplicated.append(clean)
        return {"categorized": categorized, "all_skills": deduplicated}

    @classmethod
    def _recover_skills_from_context(cls, work_experience: list[dict[str, Any]], projects: list[dict[str, Any]]) -> dict[str, Any]:
        """Synthesize baseline skills from responsibilities and projects when a formal skills section is missing."""
        recovered_skills: set[str] = set()
        
        # We look for Capitalized Words or common technical terms in bullet points
        # to avoid dumping entire sentences into skills
        def extract_terms(text: str) -> list[str]:
            text = re.sub(r"[,;&|\.]+", " ", text)
            # Find contiguous capitalized words (e.g., "Quality Control", "React Native", "Gas Chromatography")
            # or known specific terms if they were lowercased
            capitalized = re.findall(r"\b[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*\b", text)
            return [t.strip() for t in capitalized if len(t) > 3 and not cls._is_junk_skill(t.lower())]

        for exp in work_experience:
            for resp in exp.get("responsibilities", []):
                recovered_skills.update(extract_terms(resp))
        for proj in projects:
            if proj.get("description"):
                recovered_skills.update(extract_terms(proj["description"]))
                
        deduped = sorted(list(recovered_skills))
        return {"categorized": {"Recovered Context Skills": deduped} if deduped else {}, "all_skills": deduped}

    @staticmethod
    def _extract_projects(lines: list[str]) -> list[dict[str, Any]]:
        projects: list[dict[str, Any]] = []
        current: dict[str, Any] = {}
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(("##", "###")):
                if current.get("name"):
                    projects.append(current)
                current = {"name": line.replace("#", "").strip()}
            elif "|" in line and not line.startswith("-"):
                current["technologies"] = [value.strip() for value in line.split("|") if value.strip()]
            elif line.startswith(("-", "•")):
                current.setdefault("bullet_points", []).append(line.lstrip("-• ").strip())
            else:
                current["description"] = " ".join(filter(None, (current.get("description"), line)))
        if current.get("name"):
            projects.append(current)
        return projects

    @classmethod
    def _is_valid_name(cls, candidate: str, email: str | None, phone: str | None, location: str | None) -> bool:
        if not candidate or len(candidate) < 2 or len(candidate) > 45 or re.search(r"\d", candidate):
            return False
        if any(value in candidate.lower() for value in ("@", "http", "www.", ".com", "github", "linkedin")):
            return False
        if re.search(r"[:|]", candidate):
            return False
        # Reject single-word names ending with period (e.g. "job.")
        stripped = candidate.strip()
        if stripped.endswith(".") and " " not in stripped:
            return False
        tokens = [token for token in candidate.split() if token]
        if not 1 <= len(tokens) <= 4:
            return False
        if any(token.startswith(".") for token in tokens):
            return False
        normalized_candidate = re.sub(r"\s+", " ", candidate.lower().strip(" .:-"))
        if normalized_candidate in _NON_NAME_FIELD_LABELS:
            return False
        if cls._SECTION_HEADING.fullmatch(candidate.strip(" #*:-")):
            return False
        normalized_headings = {
            re.sub(r"\s+", " ", str(heading).lower().strip(" #* .:-"))
            for heading in cls.GENERIC_SECTION_HEADERS | cls.RESUME_HEADER_KEYWORDS
        }
        if normalized_candidate in normalized_headings:
            return False
        upper_tokens = [token.upper() for token in tokens]
        denied = cls.JOB_TITLE_KEYWORDS | cls.RESUME_HEADER_KEYWORDS
        first_token = re.sub(r"[^A-Z]", "", upper_tokens[0])
        field_labels = {label.upper() for label in _LABEL_PREFIX_DENYLIST} | {
            "STATE", "NATIONALITY", "GENDER", "DOB", "BIRTH", "MARITAL", "PIN", "PINCODE",
        }
        if first_token in field_labels:
            return False
        if len(tokens) == 1 and upper_tokens[0] in denied:
            return False
        if sum(token in denied for token in upper_tokens) >= len(tokens) * 0.5:
            return False
        # Reject configured role phrases without baking industries or technologies into extraction code.
        role_terms = cls._configured_job_title_terms()
        for term in role_terms:
            role_pattern = r"\s+".join(re.escape(part) for part in term.split())
            if role_pattern and re.search(rf"\b{role_pattern}\b", candidate, re.IGNORECASE):
                return False
        # Reject names that look like company names
        try:
            company_suffixes = RuleConfigManager.get_keywords("company_name", "suffixes")
        except KeyError:
            company_suffixes = set()
            
        if company_suffixes:
            pattern = r"\b(" + "|".join(re.escape(s) for s in company_suffixes) + r")\b"
            if re.search(pattern, candidate, re.IGNORECASE):
                return False
        return not any(value and (candidate in value or value in candidate) for value in (email, phone, location))

    @staticmethod
    def _clean_name_line(line: str) -> str:
        clean_line = line.strip().lstrip("#*->•: ").rstrip(" *#:")
        return re.sub(r"^name\s*[.:-]*\s*", "", clean_line, flags=re.IGNORECASE).strip()

    @classmethod
    def _name_from_labeled_field(cls, line: str) -> str | None:
        """Extract a name from a merged personal-details line without consuming adjacent fields."""
        for match in cls._INLINE_NAME_LABEL.finditer(line):
            if cls._INLINE_NAME_OWNER.search(line[:match.start()]):
                continue
            value = line[match.end():]
            boundary = cls._INLINE_FIELD_BOUNDARY.search(value)
            if boundary:
                value = value[:boundary.start()]
            value = re.sub(r"^(?:mr|mrs|ms|miss|dr)\.?\s+", "", value.strip(), flags=re.IGNORECASE)
            value = value.strip(" -*|:;,.")
            if 1 <= len(value.split()) <= 4:
                return value
        return None

    @staticmethod
    def _name_structure_score(candidate: str, index: int, text_lines: list[str]) -> int:
        """Rank structurally plausible names without relying on a person's vocabulary."""
        token_count = len(candidate.split())
        score = 4 if 2 <= token_count <= 4 else 0
        raw_line = text_lines[index].strip() if 0 <= index < len(text_lines) else ""
        previous_line = text_lines[index - 1].strip() if index > 0 else ""
        if re.match(r"^(?:#+\s*)?name\s*[.:-]", raw_line, re.IGNORECASE):
            score += 6
        if re.fullmatch(r"(?:#+\s*)?name\s*[.:-]*", previous_line, re.IGNORECASE):
            score += 6
        if index < 6:
            score += 2
        return score

    @classmethod
    def _name_from_combined_header(cls, line: str) -> str | None:
        """Recover a name from OCR/PDF lines that merge decorative text, name, and role."""
        if not line:
            return None

        tokens = line.split()
        collapsed: list[tuple[str, bool]] = []
        index = 0
        while index < len(tokens):
            if len(tokens[index]) == 1 and tokens[index].isalpha():
                letters: list[str] = []
                while index < len(tokens) and len(tokens[index]) == 1 and tokens[index].isalpha():
                    letters.append(tokens[index])
                    index += 1
                collapsed.append(("".join(letters) if len(letters) >= 2 else letters[0], len(letters) >= 2))
                continue
            collapsed.append((tokens[index], False))
            index += 1

        normalized = " ".join(token for token, _ in collapsed)
        title_boundary = cls._find_job_title_boundary(normalized)
        if title_boundary is None:
            return None

        prefix = normalized[:title_boundary].strip(" -|:")
        prefix_tokens = prefix.split()
        spaced_token_index = next((idx for idx, (_, from_spaced_run) in enumerate(collapsed[:len(prefix_tokens)]) if from_spaced_run), None)
        if spaced_token_index is not None and spaced_token_index > 0:
            prefix_tokens = prefix_tokens[spaced_token_index:]

        header_terms = RuleConfigManager.get_keywords("name", "header_denylist")
        while prefix_tokens and prefix_tokens[0].lower().strip(".:-") in header_terms:
            prefix_tokens.pop(0)
        if not 1 <= len(prefix_tokens) <= 4:
            return None
        return " ".join(prefix_tokens).title()

    @classmethod
    def _find_job_title_boundary(cls, value: str) -> int | None:
        """Locate the first configured role phrase, including when OCR glues it to a name token."""
        if not value:
            return None
        boundaries: list[tuple[int, int]] = []
        for raw_term in cls._configured_job_title_terms():
            term = raw_term.strip()
            compact_length = len(re.sub(r"\W", "", term))
            if compact_length < 2:
                continue
            pattern = r"\s+".join(re.escape(part) for part in term.split())
            for match in re.finditer(pattern, value, re.IGNORECASE):
                before_is_boundary = match.start() == 0 or not value[match.start() - 1].isalnum()
                after_is_boundary = match.end() == len(value) or not value[match.end()].isalnum()
                if after_is_boundary and (before_is_boundary or compact_length >= 4):
                    boundary_start = match.start()
                    seniority_prefix = re.search(
                        r"\b(?:sr\.?|senior|jr\.?|junior|lead|principal|staff|chief|head)\s+(?:[\w.+#-]+\s+){0,2}$",
                        value[:match.start()],
                        re.IGNORECASE,
                    )
                    if seniority_prefix:
                        boundary_start = seniority_prefix.start()
                    boundaries.append((boundary_start, -compact_length))
        return min(boundaries)[0] if boundaries else None

    @classmethod
    def _configured_job_title_terms(cls) -> set[str]:
        """Build name-rejection role terms from governed config and active taxonomy."""
        terms = set(RuleConfigManager.get_keywords("name", "job_title_denylist"))
        try:
            from app.repositories.department_domain import department_domain_repository

            for domain in department_domain_repository.get_all_domains():
                for role in domain.default_roles:
                    clean_role = str(role).strip().lower()
                    if not clean_role:
                        continue
                    terms.add(clean_role)
                    final_token = re.sub(r"[^a-z]", "", clean_role.split()[-1])
                    if len(final_token) >= 4:
                        terms.add(final_token)
        except Exception:
            pass
        return terms

    @staticmethod
    def _email_name_tokens(email: str | None) -> list[str]:
        if not email:
            return []
        local_part = re.sub(r"\d+", "", email.split("@", 1)[0].lower())
        return [token for token in re.split(r"[._\-\s]+", local_part) if len(token) >= 2]

    _SYNTHETIC_NAME_DENYLIST: frozenset[str] = frozenset({
        "candidatecvfilename", "candidatephotofilename", "candidatecv", "cv", "resume",
        "document", "upload", "attachment", "file", "unknown candidate", "profile",
        "candidatename", "filename", "candidate", "applicant",
    })

    @classmethod
    def _name_from_filename(cls, filename: str | None) -> str | None:
        if not filename:
            return None
        clean_name = re.sub(r"\.(pdf|docx)$", "", str(filename).strip(), flags=re.IGNORECASE)
        # Strip synthetic timestamp/ID patterns like 1761533883_CandidateCVFileName_13672 or cv_...
        clean_name = re.sub(r"^cv_", "", clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r"^\d{8,12}_", "", clean_name)
        clean_name = re.sub(r"_\d+$", "", clean_name)

        # Check against technical denylist
        normalized_token = re.sub(r"[^a-zA-Z]", "", clean_name).lower()
        if not normalized_token or normalized_token in cls._SYNTHETIC_NAME_DENYLIST:
            return None

        clean_name = re.sub(r"[-_](cv|resume|updated|\d+)", "", clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r"[-_]+", " ", clean_name).strip()
        result = " ".join(word.capitalize() for word in clean_name.split())
        final_token = re.sub(r"[^a-zA-Z]", "", result).lower()
        if not result or final_token in cls._SYNTHETIC_NAME_DENYLIST:
            return None
        return result

    @staticmethod
    def _first_match(pattern: str, text: str) -> str | None:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(0) if match else None


ResumeJsonExtractor = ResumeFieldExtractor
