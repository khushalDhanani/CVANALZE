import re
from typing import Any

from app.core.logging import logger
from app.core.rule_config_manager import RuleConfigManager
from app.services.dynamic_geo_heading_service import DynamicGeoAndHeadingService
from app.services.resume_normalizer import ResumeNormalizer


class classproperty:
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        return self.func(owner)


class ResumeFieldExtractor:
    _SECTION_HEADING = re.compile(
        r"^(?:#+|\*\*)\s*(SUMMARY|PROFILE SUMMARY|PROFILE|WORK EXPERIENCE|EXPERIENCE|EMPLOYMENT|EDUCATION|SKILLS|TECHNICAL SKILLS|PROJECTS|CERTIFICATIONS|LANGUAGES|HOBBIES|CONTACT)\b",
        re.IGNORECASE,
    )
    _DATE_PART = (
        r"(?:"
        r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(?:\d{1,2}[,\s]+)?"
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
        + r"|\b(?:present|current|now|till date|to date|onwards|till now|currently|presently)\b"
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
                candidates.append((candidate, any(word in email_tokens for word in words)))

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
            if "EXPERIENCE" in heading or "EMPLOYMENT" in heading:
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

    @classmethod
    def _extract_employment(cls, lines: list[str]) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        current: dict[str, Any] = {}

        def commit() -> None:
            nonlocal current
            if current.get("company") or current.get("job_title") or current.get("responsibilities"):
                jobs.append(current)
            current = {}

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            date_match = cls._DATE_RANGE.search(line)
            if line.startswith(("##", "###")):
                commit()
                company = line.replace("#", "").strip()
                if cls.is_valid_company_name(company):
                    current["company"] = company
                continue
            if date_match:
                if current.get("dates") or (current.get("responsibilities") and len(current.get("responsibilities", [])) > 1):
                    commit()
                current["dates"] = date_match.group(0)
                possible_title = cls._DATE_RANGE.sub("", line).strip(" ()-|–—")
                title_company_match = re.match(r"(.+?)\s+at\s+(.+)$", possible_title, re.IGNORECASE)
                if title_company_match:
                    possible_title = title_company_match.group(1).strip()
                    possible_company = title_company_match.group(2).strip()
                    if possible_company and cls.is_valid_company_name(possible_company):
                        current["company"] = possible_company
                if possible_title and cls.is_valid_job_title(possible_title):
                    current["job_title"] = possible_title
                continue
            if line.startswith(("-", "•")):
                current.setdefault("responsibilities", []).append(line.lstrip("-• ").strip())
            elif not current.get("job_title") and cls.is_valid_job_title(line):
                current["job_title"] = line
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
    def _extract_skills(lines: list[str]) -> dict[str, Any]:
        categorized: dict[str, list[str]] = {}
        all_skills: list[str] = []
        for raw_line in lines:
            line = raw_line.lstrip("-• ").strip()
            if not line:
                continue
            if ":" in line:
                category, values = line.split(":", 1)
                items = [item.strip() for item in re.split(r"[,;&|]+", values) if item.strip()]
                categorized[category.strip()] = items
            else:
                items = [item.strip() for item in re.split(r"[,;&|]+", line) if item.strip()]
            all_skills.extend(items)
        deduplicated: list[str] = []
        seen: set[str] = set()
        for skill in all_skills:
            if skill.lower() not in seen:
                seen.add(skill.lower())
                deduplicated.append(skill)
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
        tokens = [token for token in candidate.split() if token]
        if not 1 <= len(tokens) <= 4:
            return False
        upper_tokens = [token.upper() for token in tokens]
        denied = cls.JOB_TITLE_KEYWORDS | cls.RESUME_HEADER_KEYWORDS
        if len(tokens) == 1 and upper_tokens[0] in denied:
            return False
        if sum(token in denied for token in upper_tokens) >= len(tokens) * 0.5:
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
