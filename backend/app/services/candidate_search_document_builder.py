from __future__ import annotations
import re
from typing import Any

from app.services.candidate_vector_extractor import CandidateVectorTextExtractor


class CandidateSearchDocumentBuilder:
    """
    Dynamic Candidate Search Document & Section Text Builder.
    Constructs multi-vector section texts and weighted PostgreSQL FTS TSVector documents from candidate data.
    Does NOT use hardcoded domain/technology lists.
    """

    @classmethod
    def build_section_texts(
        cls,
        markdown_text: str,
        resume_json: dict[str, Any] | None = None,
        candidate_domain_profile: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """
        Build text dictionary for all candidate sections:
        profile, skills, experience, projects, education, certifications, domain, full_text.
        """
        sections = CandidateVectorTextExtractor.build_section_texts(
            markdown_text, resume_json, candidate_domain_profile
        )

        resume_dict = resume_json or {}

        # Add education and certifications section texts dynamically
        education_text = cls.extract_education_text(markdown_text, resume_dict)
        certifications_text = cls.extract_certifications_text(markdown_text, resume_dict)

        sections["education"] = education_text
        sections["certifications"] = certifications_text
        sections["full_text"] = markdown_text.strip() if markdown_text else ""

        return sections

    @classmethod
    def extract_education_text(cls, markdown_text: str, resume_json: dict[str, Any]) -> str:
        parts: list[str] = []
        education_list = resume_json.get("education") or []
        if isinstance(education_list, list):
            for edu in education_list:
                if isinstance(edu, dict):
                    deg = edu.get("degree") or edu.get("qualification")
                    field_of_study = edu.get("field_of_study") or edu.get("domain") or edu.get("major")
                    inst = edu.get("institution") or edu.get("school") or edu.get("university")
                    edu_str = f"Degree: {deg or 'N/A'}"
                    if field_of_study:
                        edu_str += f" in {field_of_study}"
                    if inst:
                        edu_str += f" at {inst}"
                    parts.append(edu_str)
                elif isinstance(edu, str) and edu.strip():
                    parts.append(edu.strip())

        if not parts and markdown_text:
            from app.services.resume_field_extractor import ResumeFieldExtractor
            sec = ResumeFieldExtractor._split_sections(markdown_text.splitlines())
            edu_lines = sec.get("education", [])
            if edu_lines:
                parts.extend(edu_lines[:15])

        return "\n".join(parts).strip()

    @classmethod
    def extract_certifications_text(cls, markdown_text: str, resume_json: dict[str, Any]) -> str:
        parts: list[str] = []
        certs = resume_json.get("certifications") or resume_json.get("certificates") or []
        if isinstance(certs, list):
            for c in certs:
                if isinstance(c, dict):
                    name = c.get("name") or c.get("title") or c.get("certification")
                    issuer = c.get("issuer") or c.get("authority")
                    c_str = f"Certification: {name or 'N/A'}"
                    if issuer:
                        c_str += f" ({issuer})"
                    parts.append(c_str)
                elif isinstance(c, str) and c.strip():
                    parts.append(c.strip())

        return "\n".join(parts).strip()

    @classmethod
    def build_fts_content_snapshot(
        cls,
        markdown_text: str,
        resume_json: dict[str, Any] | None = None,
        candidate_domain_profile: dict[str, Any] | None = None,
    ) -> str:
        """
        Construct a clean snapshot text combining all weighted fields for pg_trgm trigram similarity queries.
        """
        sections = cls.build_section_texts(markdown_text, resume_json, candidate_domain_profile)
        snapshot_parts = [
            sections.get("profile", ""),
            sections.get("skills", ""),
            sections.get("experience", ""),
            sections.get("projects", ""),
            sections.get("education", ""),
            sections.get("certifications", ""),
            sections.get("domain", ""),
        ]
        return "\n".join(p for p in snapshot_parts if p).strip()

    @classmethod
    def build_tsvector_sql_expression(
        cls,
        markdown_text: str,
        resume_json: dict[str, Any] | None = None,
        candidate_domain_profile: dict[str, Any] | None = None,
    ) -> str:
        """
        Construct a PostgreSQL setweight(to_tsvector(...)) SQL expression text representation:
        - Weight A: Titles, Skills, Name
        - Weight B: Work Experience, Company names
        - Weight C: Projects, Certifications
        - Weight D: Education, Full Text
        """
        sections = cls.build_section_texts(markdown_text, resume_json, candidate_domain_profile)

        a_text = cls._sanitize_fts_input(sections.get("profile", "") + " " + sections.get("skills", ""))
        b_text = cls._sanitize_fts_input(sections.get("experience", ""))
        c_text = cls._sanitize_fts_input(sections.get("projects", "") + " " + sections.get("certifications", ""))
        d_text = cls._sanitize_fts_input(sections.get("education", "") + " " + sections.get("full_text", "")[:3000])

        return f"setweight(to_tsvector('english', '{a_text}'), 'A') || setweight(to_tsvector('english', '{b_text}'), 'B') || setweight(to_tsvector('english', '{c_text}'), 'C') || setweight(to_tsvector('english', '{d_text}'), 'D')"

    @classmethod
    def _sanitize_fts_input(cls, text: str) -> str:
        cleaned = re.sub(r"['\\]", " ", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:5000]
