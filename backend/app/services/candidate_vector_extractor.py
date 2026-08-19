from __future__ import annotations
import re
from typing import Any


class CandidateVectorTextExtractor:
    """
    Extracts distinct semantic text prompts for multi-vector candidate representations:
    profile, skills, experience, projects, domain, and overall composite text.
    """

    @classmethod
    def build_section_texts(
        cls,
        markdown_text: str,
        resume_json: dict[str, Any] | None = None,
        candidate_domain_profile: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """
        Build text prompts for each candidate vector section.
        Returns a dictionary mapping section keys ('profile', 'skills', 'experience', 'projects', 'domain', 'overall')
        to canonical text strings suitable for vector embedding.
        """
        resume_dict = resume_json or {}
        domain_dict = candidate_domain_profile or {}

        profile_text = cls.extract_profile_text(markdown_text, resume_dict, domain_dict)
        skills_text = cls.extract_skills_text(markdown_text, resume_dict, domain_dict)
        experience_text = cls.extract_experience_text(markdown_text, resume_dict)
        projects_text = cls.extract_projects_text(markdown_text, resume_dict)
        domain_text = cls.extract_domain_text(markdown_text, resume_dict, domain_dict)
        overall_text = markdown_text.strip() if markdown_text and markdown_text.strip() else profile_text

        return {
            "profile": profile_text,
            "skills": skills_text,
            "experience": experience_text,
            "projects": projects_text,
            "domain": domain_text,
            "overall": overall_text,
        }

    @classmethod
    def extract_profile_text(
        cls,
        markdown_text: str,
        resume_json: dict[str, Any],
        domain_profile: dict[str, Any],
    ) -> str:
        parts: list[str] = []

        contact = resume_json.get("contact_info") or resume_json.get("contact") or {}
        name = contact.get("name") or contact.get("full_name")
        if name:
            parts.append(f"Candidate Name: {name}")

        job_title = contact.get("job_title") or resume_json.get("job_title")
        if job_title:
            parts.append(f"Title / Role: {job_title}")

        primary_dept = domain_profile.get("recommended_department") or domain_profile.get("primary_department")
        if primary_dept:
            parts.append(f"Primary Department: {primary_dept}")

        prof_domain = domain_profile.get("professional_domain")
        if prof_domain:
            parts.append(f"Professional Domain: {prof_domain}")

        strengths = domain_profile.get("strengths") or []
        if strengths:
            str_text = ", ".join(strengths) if isinstance(strengths, list) else str(strengths)
            parts.append(f"Strengths: {str_text}")

        summary = resume_json.get("summary") or resume_json.get("professional_summary") or resume_json.get("objective")
        if summary:
            parts.append(f"Summary: {summary}")

        if not parts and markdown_text:
            lines = [line.strip() for line in markdown_text.splitlines() if line.strip()]
            parts.append(" ".join(lines[:10]))

        return "\n".join(parts).strip()

    @classmethod
    def extract_skills_text(
        cls,
        markdown_text: str,
        resume_json: dict[str, Any],
        domain_profile: dict[str, Any],
    ) -> str:
        skills: list[str] = []

        raw_skills = resume_json.get("skills")
        if isinstance(raw_skills, list):
            skills.extend(str(s) for s in raw_skills if isinstance(s, str) or isinstance(s, dict))
        elif isinstance(raw_skills, dict):
            if isinstance(raw_skills.get("all_skills"), list):
                skills.extend(str(s) for s in raw_skills["all_skills"] if s)
            for sub_list in raw_skills.values():
                if isinstance(sub_list, list):
                    skills.extend(str(s) for s in sub_list if s)

        strengths = domain_profile.get("strengths") or []
        for st in strengths:
            if isinstance(st, str) and "Core Skills:" in st:
                skills.append(st.replace("Core Skills:", "").strip())

        certs = resume_json.get("certifications") or resume_json.get("certificates")
        if certs:
            cert_str = ", ".join(certs) if isinstance(certs, list) else str(certs)
            skills.append(f"Certifications: {cert_str}")

        if not skills and markdown_text:
            from app.services.resume_field_extractor import ResumeFieldExtractor
            sections = ResumeFieldExtractor._split_sections(markdown_text.splitlines())
            skill_lines = sections.get("skills", [])
            if skill_lines:
                skills.extend(skill_lines)

        dedup_skills: list[str] = []
        seen: set[str] = set()
        for s in skills:
            s_clean = re.sub(r"\s+", " ", str(s)).strip()
            s_key = s_clean.lower()
            if s_clean and s_key not in seen:
                seen.add(s_key)
                dedup_skills.append(s_clean)

        return "Candidate Skills & Competencies: " + ", ".join(dedup_skills) if dedup_skills else ""

    @classmethod
    def extract_experience_text(
        cls,
        markdown_text: str,
        resume_json: dict[str, Any],
    ) -> str:
        parts: list[str] = []

        experiences = resume_json.get("work_experience") or resume_json.get("experience") or resume_json.get("employment") or []
        if isinstance(experiences, list):
            for exp in experiences:
                if isinstance(exp, dict):
                    title = exp.get("job_title") or exp.get("title") or exp.get("position")
                    company = exp.get("company") or exp.get("company_name")
                    duration = exp.get("duration") or exp.get("dates")
                    exp_header = f"Role: {title or 'N/A'}"
                    if company:
                        exp_header += f" at {company}"
                    if duration:
                        exp_header += f" ({duration})"
                    parts.append(exp_header)

                    resps = exp.get("responsibilities") or exp.get("highlights") or exp.get("description") or []
                    if isinstance(resps, list) and resps:
                        parts.append("Responsibilities: " + "; ".join(str(r) for r in resps if r))
                    elif isinstance(resps, str) and resps.strip():
                        parts.append(f"Responsibilities: {resps.strip()}")
                elif isinstance(exp, str) and exp.strip():
                    parts.append(exp.strip())

        if not parts and markdown_text:
            from app.services.resume_field_extractor import ResumeFieldExtractor
            sections = ResumeFieldExtractor._split_sections(markdown_text.splitlines())
            exp_lines = sections.get("experience", [])
            if exp_lines:
                parts.extend(exp_lines[:25])

        return "\n".join(parts).strip()

    @classmethod
    def extract_projects_text(
        cls,
        markdown_text: str,
        resume_json: dict[str, Any],
    ) -> str:
        parts: list[str] = []

        projects = resume_json.get("projects") or resume_json.get("project_experience") or []
        if isinstance(projects, list):
            for proj in projects:
                if isinstance(proj, dict):
                    title = proj.get("title") or proj.get("name") or proj.get("project_name")
                    desc = proj.get("description") or proj.get("summary") or proj.get("details")
                    tech = proj.get("technologies") or proj.get("tools") or proj.get("tech_stack")
                    p_str = f"Project: {title or 'N/A'}"
                    if desc:
                        p_str += f" - {desc}"
                    if tech:
                        tech_str = ", ".join(tech) if isinstance(tech, list) else str(tech)
                        p_str += f" [Tech: {tech_str}]"
                    parts.append(p_str)
                elif isinstance(proj, str) and proj.strip():
                    parts.append(proj.strip())

        if not parts and markdown_text:
            from app.services.resume_field_extractor import ResumeFieldExtractor
            sections = ResumeFieldExtractor._split_sections(markdown_text.splitlines())
            proj_lines = sections.get("projects", [])
            if proj_lines:
                parts.extend(proj_lines[:20])

        return "\n".join(parts).strip()

    @classmethod
    def extract_domain_text(
        cls,
        markdown_text: str,
        resume_json: dict[str, Any],
        domain_profile: dict[str, Any],
    ) -> str:
        parts: list[str] = []

        rec_dept = domain_profile.get("recommended_department") or domain_profile.get("primary_department")
        if rec_dept:
            parts.append(f"Department: {rec_dept}")

        prof_domain = domain_profile.get("professional_domain")
        if prof_domain:
            parts.append(f"Domain: {prof_domain}")

        suitable_roles = domain_profile.get("suitable_job_roles") or []
        if suitable_roles:
            roles_str = ", ".join(suitable_roles) if isinstance(suitable_roles, list) else str(suitable_roles)
            parts.append(f"Target Roles: {roles_str}")

        if not parts and markdown_text:
            from app.services.candidate_domain_service import CandidateDomainService
            parts.append(CandidateDomainService.build_domain_candidate_text(markdown_text))

        return "\n".join(parts).strip()
