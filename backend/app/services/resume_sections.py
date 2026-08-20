from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class SectionKind(StrEnum):
    GENERAL = "general"
    CONTACT = "contact"
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    PROJECTS = "projects"
    SKILLS = "skills"
    CERTIFICATIONS = "certifications"
    LANGUAGES = "languages"
    INTERESTS = "interests"
    SAFETY = "safety"
    COMPETENCIES = "competencies"
    DECLARATION = "declaration"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ResumeSection:
    kind: SectionKind
    heading: str | None
    lines: tuple[str, ...]
    start_line: int
    end_line: int
    confidence: float
    reason: str


@dataclass(frozen=True)
class SectionDetectionResult:
    sections: tuple[ResumeSection, ...]

    def blocks(self, kind: SectionKind) -> tuple[ResumeSection, ...]:
        return tuple(section for section in self.sections if section.kind == kind)

    def lines(self, kind: SectionKind) -> list[str]:
        return [line for section in self.blocks(kind) for line in section.lines]


class ResumeSectionDetector:
    """Deterministically classify resume sections without promoting unknown headings."""

    POLICY_VERSION = "section-integrity-1.0.0"
    MAX_SECTIONS = 256
    MAX_TOTAL_LINES = 50_000
    MAX_LINES_PER_SECTION = 10_000
    MAX_LINE_CHARS = 10_000
    _MARKDOWN_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
    _DECORATION = re.compile(r"^[\s\-*•·_=|:]+|[\s\-*•·_=|:]+$")
    _ALIASES: dict[SectionKind, frozenset[str]] = {
        SectionKind.CONTACT: frozenset({"contact", "contact details", "contact information", "personal details"}),
        SectionKind.SUMMARY: frozenset({
            "summary", "profile", "profile summary", "professional summary",
            "professional profile summary", "executive summary", "career objective", "objective", "overview",
        }),
        SectionKind.EXPERIENCE: frozenset({
            "experience", "work experience", "working experience", "professional experience",
            "employment", "employment history", "work history", "career history", "career highlights",
            "professional background", "relevant experience", "present employment", "current employment",
            "practical exposure", "experience summary", "career graph", "career path",
            "employment record", "employment details", "work record", "experience highlights",
        }),
        SectionKind.EDUCATION: frozenset({
            "education", "educational background", "education background", "academic background",
            "academics", "academic qualifications", "educational qualifications", "qualifications",
            "education and qualifications", "academic profile",
            "education details", "academic details", "scholastic record",
        }),
        SectionKind.PROJECTS: frozenset({
            "project", "projects", "selected projects", "key projects", "academic projects",
            "personal projects", "project work", "project experience", "key project experience",
            "projects and experience",
            "project and experience", "projects undertaken", "major projects",
        }),
        SectionKind.SKILLS: frozenset({
            "skills", "technical skills", "professional skills", "professional skill", "key skills",
            "core skills", "skills and tools", "skills and expertise", "expertise", "areas of expertise",
            "technical expertise", "technical competencies", "technical proficiency", "technical proficiencies",
            "computer proficiency", "computer proficiencies", "computer skills", "software skills",
            "software proficiency", "it skills", "tools and technologies", "tools and technology",
            "technology stack", "technologies", "instrument handling", "instruments handled",
            "equipment handling",
        }),
        SectionKind.CERTIFICATIONS: frozenset({"certifications", "certification", "certificates", "licenses", "courses"}),
        SectionKind.LANGUAGES: frozenset({"languages", "language", "languages known"}),
        SectionKind.INTERESTS: frozenset({"interests", "hobbies", "hobbies and interests"}),
        SectionKind.SAFETY: frozenset({"safety", "safety and compliance", "health and safety", "ehs"}),
        SectionKind.COMPETENCIES: frozenset({"core competencies", "competencies", "key competencies"}),
        SectionKind.DECLARATION: frozenset({"declaration", "references", "reference"}),
    }
    _LOOKUP: dict[str, SectionKind] = {}
    for _kind, _aliases in _ALIASES.items():
        for _alias in _aliases:
            _LOOKUP[_alias] = _kind
    del _alias, _aliases, _kind

    @classmethod
    def normalize_heading(cls, value: str) -> str:
        heading = value.strip()
        markdown = cls._MARKDOWN_HEADING.match(heading)
        if markdown:
            heading = markdown.group(1)
        heading = heading.strip("*# ")
        heading = heading.replace("&", " and ")
        heading = re.sub(r"[\u2013\u2014/_]+", " ", heading)
        heading = re.sub(r"[^\w.+ -]", " ", heading, flags=re.UNICODE)
        return re.sub(r"\s+", " ", heading).strip().casefold()

    @classmethod
    def classify_heading(cls, value: str) -> SectionKind | None:
        normalized = cls.normalize_heading(value)
        return cls._LOOKUP.get(normalized)

    @classmethod
    def _is_explicit_heading(cls, raw_line: str) -> bool:
        if cls._MARKDOWN_HEADING.match(raw_line):
            return True
        stripped = cls._DECORATION.sub("", raw_line.strip())
        if not stripped or len(stripped) > 80 or len(stripped.split()) > 8:
            return False
        return cls.classify_heading(stripped) is not None

    @classmethod
    def detect(cls, lines: list[str]) -> SectionDetectionResult:
        sections: list[ResumeSection] = []
        current_kind = SectionKind.GENERAL
        current_heading: str | None = None
        current_lines: list[str] = []
        current_start = 0
        current_heading_level: int | None = None

        def append_line(raw_line: str) -> None:
            if len(current_lines) < cls.MAX_LINES_PER_SECTION:
                current_lines.append(raw_line[: cls.MAX_LINE_CHARS])

        def commit(end_line: int) -> None:
            nonlocal current_lines
            if current_lines or current_heading is not None or not sections:
                sections.append(
                    ResumeSection(
                        kind=current_kind,
                        heading=current_heading,
                        lines=tuple(current_lines[: cls.MAX_LINES_PER_SECTION]),
                        start_line=current_start,
                        end_line=max(current_start, end_line),
                        confidence=1.0 if current_heading else 0.5,
                        reason="recognized_heading" if current_heading else "document_preamble",
                    )
                )
            current_lines = []

        bounded_lines = lines[: cls.MAX_TOTAL_LINES]
        for index, raw_line in enumerate(bounded_lines):
            if len(sections) >= cls.MAX_SECTIONS - 1:
                append_line(raw_line)
                continue
            markdown = cls._MARKDOWN_HEADING.match(raw_line)
            stripped_line = raw_line.lstrip()
            heading_level = len(stripped_line) - len(stripped_line.lstrip("#")) if markdown else None
            explicit_heading = cls._is_explicit_heading(raw_line)
            kind = cls.classify_heading(raw_line) if explicit_heading else None
            if markdown and kind is None:
                if current_heading_level is not None and heading_level is not None and heading_level > current_heading_level:
                    append_line(raw_line)
                    continue
                kind = SectionKind.UNKNOWN
            if kind is None:
                append_line(raw_line)
                continue
            commit(index - 1)
            current_kind = kind
            current_heading = (markdown.group(1) if markdown else cls._DECORATION.sub("", raw_line.strip())).strip(" *#:")
            current_start = index
            current_heading_level = heading_level

        commit(len(bounded_lines) - 1)
        return SectionDetectionResult(sections=tuple(sections))
