from __future__ import annotations
import json
from typing import Any
from app.services.context_packer import pack_cv_context
from app.services.llm_input_security import harden_prompt, sanitize_string_list, sanitize_untrusted_text

PROMPT_VERSION = "1.2"

_MANDATORY_TERMS = ("must", "required", "mandatory", "essential")


def _as_sanitized_list(value: Any) -> list[str]:
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return sanitize_string_list(values)


def _explicitly_mandatory(value: str, *, default: bool = False) -> bool:
    normalized = value.lower()
    if default:
        return True
    if any(phrase in normalized for phrase in ("not required", "not mandatory", "optional", "preferred")):
        return False
    return any(term in normalized for term in _MANDATORY_TERMS)


def build_job_requirements(job: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize supported vacancy fields into stable requirement records for LLM assessment."""
    requirements: list[dict[str, Any]] = []

    def add(category: str, values: Any, *, mandatory: bool = False, prefix: str | None = None) -> None:
        for index, value in enumerate(_as_sanitized_list(values), start=1):
            requirements.append(
                {
                    "requirement_id": f"{prefix or category.lower()}_{index}",
                    "requirement": value,
                    "category": category,
                    "mandatory": _explicitly_mandatory(value, default=mandatory),
                    "jd_evidence": value,
                }
            )

    required_skills = job.get("required_skills") or []
    if required_skills:
        add("SKILL", required_skills, mandatory=bool(job.get("required_skills_are_mandatory", True)), prefix="skill")
    if job.get("preferred_keywords"):
        add("PREFERRED_KEYWORD", job["preferred_keywords"], prefix="preferred_keyword")
    if job.get("min_experience_years") is not None:
        add("EXPERIENCE", f"Minimum {job['min_experience_years']} years of relevant experience", mandatory=True, prefix="min_experience")
    if job.get("max_experience_years") is not None:
        add("EXPERIENCE", f"Maximum {job['max_experience_years']} years of relevant experience", mandatory=True, prefix="max_experience")

    education = job.get("education_requirements") or job.get("required_education") or job.get("education")
    if education:
        add("EDUCATION", education, mandatory=True, prefix="education")
    if job.get("certifications"):
        add("CERTIFICATION", job["certifications"], prefix="certification")
    if job.get("technologies"):
        add("TECHNOLOGY", job["technologies"], prefix="technology")
    if job.get("responsibilities"):
        add("RESPONSIBILITY", job["responsibilities"], prefix="responsibility")

    description = job.get("job_description") or job.get("description")
    if description:
        sanitized_description = sanitize_untrusted_text(str(description)).text
        add("DESCRIPTION", sanitized_description, prefix="description")
    return requirements


def build_cv_job_prompt(cv_text: str, job: dict[str, Any]) -> str:
    """
    Builds a strict JSON-only prompt for Qwen to analyze a CV against job requirements.
    Provides structured JSON input instead of string concatenation to optimize Qwen's contextual understanding.
    """
    job_title = sanitize_untrusted_text(str(job.get("title", "Unknown Title"))).text
    req_skills = sanitize_string_list(job.get("required_skills", []))
    pref_keywords = sanitize_string_list(job.get("preferred_keywords", []))
    requirements = build_job_requirements(job)

    structured_input = {
        "task_instructions": (
            "You are an expert HR recruitment assistant. "
            "Analyze the candidate_cv_markdown against the job_requirements. "
            "Assess every supplied requirement separately using only grounded CV and JD evidence. "
            "Related-skill inferences must name the explicit CV fact supporting the inference. "
            "Confidence describes evidence certainty, impact describes recruiting impact, and neither is a match score."
        ),
        "job_requirements": {
            "job_title": job_title,
            "required_skills": req_skills,
            "preferred_keywords": pref_keywords,
            "requirements": requirements,
        },
        "candidate_cv_markdown": pack_cv_context(cv_text, max_tokens=1200, deidentify=True).text,
    }

    input_json = json.dumps(structured_input, indent=2, ensure_ascii=False)

    from app.services.prompt_service import PromptService
    prompt = PromptService.get_prompt(
        prompt_name="match_analysis",
        placeholders={"input_json": input_json}
    )
    return harden_prompt(prompt)
