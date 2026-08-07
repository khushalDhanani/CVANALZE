from __future__ import annotations
import re
from typing import Any

from app.core.logging import logger
from app.core.rule_config_manager import RuleConfigManager
from app.services.dynamic_geo_heading_service import DynamicGeoAndHeadingService
from app.services.resume_normalizer import ResumeNormalizer

_COMPANY_SUFFIXES = re.compile(
    r"\b(ltd|limited|pvt|private|inc|incorporated|llc|llp|corp|corporation|industries|solutions|enterprises|infosys|infotech|technologies|pharma|chemicals|remedies|generics|organics|techno\s*labs?)\b",
    re.IGNORECASE,
)
_TECH_LOCATION_BLACKLIST = {
    "provider", "getx", "bloc", "riverpod", "react", "flutter", "dart",
    "angular", "vue", "redux", "mobx", "kotlin", "swift", "java",
    "firebase", "nodejs", "django", "fastapi", "springboot",
}


class classproperty:
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        return self.func(owner)


class ResumeFieldExtractor:
    _SECTION_HEADING = re.compile(
        r"^(?:#+|\*\*)\s*(SUMMARY|PROFILE SUMMARY|PROFILE|WORK EXPERIENCE|WORKING EXPERIENCE|PROFESSIONAL EXPERIENCE|PRACTICAL EXPOSURE|EXPERIENCE|EMPLOYMENT|EDUCATION|SKILLS|TECHNICAL SKILLS|PROJECTS|CERTIFICATIONS|LANGUAGES|HOBBIES|CONTACT)\b",
        re.IGNORECASE,
    )
    _DATE_PART = (
        r"(?:"
        r"(?:\d{1,2}(?:st|nd|rd|th)?\s+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?[,\s]+"
        r"(?:19|20)\d{2}"
        r"|(?:0?[1-9]|[12]\d|3[01])[/\.\-](?:0?[1-9]|1[0-2])[/\.\-](?:19|20)\d{2}"
        r"|"
        r"(?:19|20)\d{2}"
        r"|(?:0?[1-9]|1[0-2])[/\.\-](?:19|20)\d{2}"
        r"|(?:19|20)\d{2}[/\.\-](?:0?[1-9]|1[0-2])"
        r"|(?:Q[1-4]|Summer|Winter|Spring|Fall)\s+(?:19|20)\d{2}"
        r"|(?:19|20)\d{2}"
        r")"
    )
    _END_PART = (
        r"(?:"
        + _DATE_PART
        + r"|\b\d{2}\b"
        + r"|\b(?:present|current|continue|continuing|ongoing|now|till date|to date|onwards|till now|currently|presently)\b"
        r")"
    )
    _DATE_RANGE = re.compile(
        r"(?:\b|_|\()"
        + _DATE_PART
        + r"\s*(?:[\-–—~/]|->|\bto\b|\btill\b|\buntil\b)\s*"
        + _END_PART
        + r"(?:\b|_|\))",
        re.IGNORECASE,
    )

    @classproperty
    def JOB_TITLE_KEYWORDS(cls) -> set[str]:
        return DynamicGeoAndHeadingService.get_name_denylist()

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

        # Strip common trailing job titles from line before name validation
        _title_suffix = re.compile(
            r"\s+\b(sr\.?|jr\.?|senior|junior|lead|principal|chief|head|executive|manager|director|engineer|developer|analyst|consultant|specialist|officer|architect|designer)(?:\b|\s).*$",
            re.IGNORECASE,
        )

        candidates: list[tuple[str, bool]] = []
        seen_indices: set[int] = set()
        for index in indices:
            if index in seen_indices or index >= len(text_lines):
                continue
            seen_indices.add(index)
            candidate = cls._clean_name_line(text_lines[index])
            if not candidate or "@" in candidate or "CONTACT" in candidate.upper():
                continue
            if cls._is_valid_name(candidate, email, phone, location):
                words = [word.lower() for word in candidate.split()]
                matches_email = any(
                    word in email_tokens or any(word in token or token in word for token in email_tokens if len(token) >= 3 and len(word) >= 3)
                    for word in words
                )
                candidates.append((candidate, matches_email))
            else:
                # Try stripping job title suffix
                stripped = _title_suffix.sub("", candidate).strip()
                if stripped and stripped != candidate and cls._is_valid_name(stripped, email, phone, location):
                    words = [word.lower() for word in stripped.split()]
                    matches_email = any(
                        word in email_tokens or any(word in token or token in word for token in email_tokens if len(token) >= 3 and len(word) >= 3)
                        for word in words
                    )
                    candidates.append((stripped, matches_email))

        # If no valid candidates found in header, search full document for lines matching email tokens
        if not candidates and email_tokens:
            for index, raw_l in enumerate(text_lines):
                candidate = cls._clean_name_line(raw_l)
                if not candidate or "@" in candidate:
                    continue
                cand_clean = _title_suffix.sub("", candidate).strip()
                words = [word.lower() for word in cand_clean.split()]
                matches_email = any(
                    word in email_tokens or any(word in token or token in word for token in email_tokens if len(token) >= 3 and len(word) >= 3)
                    for word in words
                )
                if matches_email and cls._is_valid_name(cand_clean, email, phone, location):
                    candidates.append((cand_clean, True))
                    break

        for candidate, matches_email in candidates:
            if matches_email:
                return (
                    candidate,
                    scores.get("header_email_validated", 0.95),
                    "HIGH",
                    "header_email_validated",
                )
        if candidates:
            return (
                candidates[0][0],
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
                if any(token in _TECH_LOCATION_BLACKLIST for token in tokens):
                    continue
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
        title_without_dates = cls._DATE_RANGE.sub("", candidate).strip(" ()-|–—")
        tokens = [token.lower() for token in re.split(r"[\s/\-&()]+", title_without_dates) if token]
        if not (1 <= len(tokens) <= max_words) or tokens[0] in cls.NARRATIVE_SENTENCE_STARTERS:
            return False
        if any(phrase in title_without_dates.lower() for phrase in cls.NARRATIVE_PHRASES):
            return False
        return any(token.upper() in cls.JOB_TITLE_KEYWORDS for token in tokens) or any(word[0].isupper() for word in title_without_dates.split() if word and word[0].isalpha())

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
            "work_experience": cls._extract_employment(sections.get("experience", [])),
            "education": cls._extract_education(sections.get("education", [])),
            "skills": cls._extract_skills(sections.get("skills", [])),
            "projects": cls._extract_projects(sections.get("projects", [])),
            "certifications": [line.lstrip("-• ").strip() for line in sections.get("certifications", []) if line.strip()],
            "quality_metrics": metrics or {},
        }
        result["normalized"] = ResumeNormalizer.normalize(result, text).model_dump(mode="json")
        return result

    @classmethod
    def _split_sections(cls, lines: list[str]) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {"general": []}
        current = "general"
        for line in lines:
            match = cls._SECTION_HEADING.match(line.strip())
            if not match:
                sections.setdefault(current, []).append(line)
                continue
            heading = match.group(1).upper()
            if "EXPERIENCE" in heading or "EMPLOYMENT" in heading or "EXPOSURE" in heading:
                current = "experience"
            elif "EDUCATION" in heading:
                current = "education"
            elif "SKILL" in heading:
                current = "skills"
            elif "PROJECT" in heading:
                current = "projects"
            elif "SUMMARY" in heading or "PROFILE" in heading:
                current = "summary"
            elif "CERTIFICATION" in heading:
                current = "certifications"
            else:
                current = heading.lower()
            sections.setdefault(current, [])
        return sections

    @staticmethod
    def _looks_like_company(text: str) -> bool:
        """Return True if text looks like a company name rather than a job title."""
        if not text:
            return False
        return bool(_COMPANY_SUFFIXES.search(text))

    @staticmethod
    def _looks_like_title(text: str) -> bool:
        """Return True if text looks like a job title rather than a company name."""
        if not text:
            return False
        title_keywords = re.compile(
            r"\b(engineer|developer|manager|executive|analyst|officer|consultant|director|lead|specialist|inspector|administrator|technician|incharge|in\s*charge|operator|assistant|chemist|scientist|programmer|architect|designer|coordinator|supervisor|head|sr\.|jr\.)\b",
            re.IGNORECASE,
        )
        return bool(title_keywords.search(text))

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
            if current.get("company") or current.get("job_title") or current.get("responsibilities"):
                cls._fix_company_title_swap(current)
                jobs.append(current)
            current = {}

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            date_match = cls._DATE_RANGE.search(line)
            if line.startswith("|") and line.endswith("|"):
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if len(cells) >= 4:
                    from app.services.date_interval_parser import DateIntervalParser

                    start_date, _ = DateIntervalParser.parse_date_point(cells[-2], is_end_date=False)
                    end_date, _ = DateIntervalParser.parse_date_point(cells[-1], is_end_date=True)
                    if start_date and (end_date or DateIntervalParser.is_present(cells[-1])):
                        commit()
                        current["job_title"] = cells[0] or "Position"
                        current["company"] = cells[1] or "Organization"
                        current["dates"] = f"{cells[-2]} - {cells[-1]}"
                    continue
            # Handle merged heading lines like "## IT Executive , BODAL CHEMICALS LTD, SAYKHA"
            if line.startswith(("##", "###")):
                commit()
                heading_text = line.replace("#", "").strip()
                if date_match:
                    current["dates"] = date_match.group(0).strip(" ()")
                    heading_text = cls._DATE_RANGE.sub("", heading_text).strip(" ()-|–—")
                # Try to split "Title , Company" or "Title, Company" in heading
                comma_parts = [p.strip() for p in heading_text.split(",", 1) if p.strip()]
                if len(comma_parts) >= 2 and cls._looks_like_company(comma_parts[1]):
                    current["job_title"] = comma_parts[0]
                    current["company"] = comma_parts[1]
                elif cls._looks_like_title(heading_text) and not cls._looks_like_company(heading_text):
                    current["job_title"] = heading_text
                elif cls.is_valid_company_name(heading_text):
                    current["company"] = heading_text
                continue
            if date_match:
                if current.get("dates"):
                    commit()
                current["dates"] = date_match.group(0).strip(" ()")
                possible_title = cls._DATE_RANGE.sub("", line).strip(" ()-|–—")
                title_company_match = re.match(r"(.+?)\s+at\s+(.+)$", possible_title, re.IGNORECASE)
                if title_company_match:
                    possible_title = title_company_match.group(1).strip()
                    possible_company = title_company_match.group(2).strip()
                    if possible_company and cls.is_valid_company_name(possible_company):
                        current["company"] = possible_company
                if possible_title:
                    if cls._looks_like_company(possible_title) and not current.get("company"):
                        current["company"] = possible_title
                    elif cls.is_valid_job_title(possible_title):
                        current["job_title"] = possible_title
                continue
            if line.startswith(("-", "•")):
                clean_bullet = line.lstrip("-• \uf0b7").strip()
                # Handle structured bullet CVs: "Duration :- dd/mm/yyyy to dd/mm/yyyy"
                duration_match = re.search(r"(?:duration|period|tenure)\s*[:\-]+\s*(.+)$", clean_bullet, re.IGNORECASE)
                if duration_match:
                    from app.services.date_interval_parser import DateIntervalParser
                    date_str = duration_match.group(1).strip()
                    d_match = cls._DATE_RANGE.search(date_str)
                    if d_match:
                        if current.get("dates") and (current.get("company") or current.get("job_title")):
                            commit()
                        current["dates"] = d_match.group(0).strip(" ()")
                        continue
                # Handle "Organization :- XYZ Ltd" bullets
                org_match = re.search(r"(?:organization|company|employer)\s*[:\-]+\s*(.+)$", clean_bullet, re.IGNORECASE)
                if org_match and org_match.group(1).strip():
                    current["company"] = org_match.group(1).strip()
                    continue
                # Handle "Designation :- Senior Engineer" bullets
                desig_match = re.search(r"(?:designation|job\s+title|role|position)\s*[:\-]+\s*(.+)$", clean_bullet, re.IGNORECASE)
                if desig_match and desig_match.group(1).strip():
                    current["job_title"] = desig_match.group(1).strip()
                    continue
                # Check if bullet itself has a date range (e.g. bulleted date lines)
                bullet_date = cls._DATE_RANGE.search(clean_bullet)
                if bullet_date:
                    remaining = cls._DATE_RANGE.sub("", clean_bullet).strip(" ()-|–—")
                    if not remaining or len(remaining) < 5:
                        # Pure date bullet — assign to current entry
                        if not current.get("dates"):
                            current["dates"] = bullet_date.group(0).strip(" ()")
                        continue
                current.setdefault("responsibilities", []).append(clean_bullet)
            elif not current.get("job_title") and cls.is_valid_job_title(line):
                # Check if the free line is actually a company name
                if cls._looks_like_company(line) and not cls._looks_like_title(line):
                    if not current.get("company"):
                        current["company"] = line
                else:
                    current["job_title"] = line
            else:
                # Check if free line is a company name (e.g. "Resonent TechnoLabs Pvt Ltd, Surat")
                if not current.get("company") and cls._looks_like_company(line):
                    current["company"] = line
                else:
                    current["description"] = " ".join(filter(None, (current.get("description"), line)))
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
        # Reject single-word names ending with period (e.g. "job.")
        stripped = candidate.strip()
        if stripped.endswith(".") and " " not in stripped:
            return False
        tokens = [token for token in candidate.split() if token]
        if not 1 <= len(tokens) <= 4:
            return False
        upper_tokens = [token.upper() for token in tokens]
        denied = cls.JOB_TITLE_KEYWORDS | cls.RESUME_HEADER_KEYWORDS
        if len(tokens) == 1 and upper_tokens[0] in denied:
            return False
        if sum(token in denied for token in upper_tokens) >= len(tokens) * 0.5:
            return False
        # Reject names that look like job titles (contain role keywords)
        _title_reject = re.compile(
            r"\b(engineer|developer|manager|executive|analyst|consultant|director|lead|specialist|officer|sr\.|jr\.|senior|junior|flutter|android|ios|production|planning|control|quality|assurance|instrumentation|coordinator|supervisor|technician|administrator|incharge|in\s*charge)\b",
            re.IGNORECASE,
        )
        if _title_reject.search(candidate):
            return False
        # Reject names that look like company names
        if _COMPANY_SUFFIXES.search(candidate):
            return False
        return not any(value and (candidate in value or value in candidate) for value in (email, phone, location))

    @staticmethod
    def _clean_name_line(line: str) -> str:
        clean_line = line.strip().lstrip("#*->•: ").rstrip(" *#:")
        return re.sub(r"^name\s*[:-]?\s*", "", clean_line, flags=re.IGNORECASE).strip()

    @staticmethod
    def _email_name_tokens(email: str | None) -> list[str]:
        if not email:
            return []
        local_part = re.sub(r"\d+", "", email.split("@", 1)[0].lower())
        return [token for token in re.split(r"[._\-\s]+", local_part) if len(token) >= 2]

    @staticmethod
    def _name_from_filename(filename: str | None) -> str | None:
        if not filename:
            return None
        clean_name = re.sub(r"\.(pdf|docx)$", "", filename, flags=re.IGNORECASE)
        clean_name = re.sub(r"[-_](cv|resume|updated|\d+)", "", clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r"[-_]+", " ", clean_name).strip()
        return " ".join(word.capitalize() for word in clean_name.split()) or None

    @staticmethod
    def _first_match(pattern: str, text: str) -> str | None:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(0) if match else None


ResumeJsonExtractor = ResumeFieldExtractor
