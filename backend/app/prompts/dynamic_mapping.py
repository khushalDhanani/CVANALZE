from __future__ import annotations
import json
from typing import Any
from app.services.context_packer import pack_cv_context
from app.services.llm_input_security import harden_prompt, sanitize_string_list, sanitize_untrusted_text

PROMPT_VERSION = "2.0"


def build_dynamic_mapping_prompt(cv_text: str, active_vacancies: list[dict[str, Any]]) -> str:
    """
    Builds a strict JSON-only prompt for Qwen to dynamically map a CV against
    a list of available active DB vacancies.
    """

    simplified_vacancies = []
    for vac in sorted(active_vacancies, key=lambda item: str(item.get("vacancy_id") or "")):
        simplified_vacancies.append(
            {
                "vacancy_id": vac.get("vacancy_id"),
                "job_profile_id": vac.get("job_profile_id"),
                "company_id": vac.get("company_id"),
                "department_id": vac.get("department_id"),
                "location_id": vac.get("location_id"),
                "job_title": sanitize_untrusted_text(str(vac.get("title") or "")).text,
                "department": sanitize_untrusted_text(str(vac.get("department") or "")).text,
                "requirements": sanitize_string_list(vac.get("required_skills", [])),
                "skills": sanitize_string_list(vac.get("preferred_keywords", [])),
            }
        )

    structured_input = {
        "task_instructions": (
            "Act as an HR semantic matching engine. "
            "Analyze candidate_cv_markdown against ONLY the records provided in active_vacancies. "
            "Infer the candidate's professional domain, roles, skills, experience, seniority, education, and relevant capabilities directly from the CV. "
            "Compare these dynamically with each vacancy's available title, profile, department, requirements, skills, experience, and other supplied fields. "
            "Recognize semantic equivalents, related terminology, transferable skills, and role similarity without relying on predefined aliases or hardcoded mappings. "
            "Rank the most relevant vacancies by evidence-based semantic fit. "
            "Return ONLY vacancies that exist in active_vacancies and preserve their EXACT database identifiers and values. "
            "Never generate, guess, modify, infer, or fabricate any database ID or master-data value. "
            "If a field or ID is not supplied by the selected vacancy record, return null for that field. "
            "Do not create a new job title, department, company, location, designation, or vacancy. "
            "Explain matches using evidence from the CV and vacancy data only."
        ),
        "active_vacancies": simplified_vacancies,
        "candidate_cv_markdown": pack_cv_context(cv_text, max_tokens=1600, deidentify=True).text,
    }

    input_json = json.dumps(structured_input, indent=2, ensure_ascii=False)

    from app.services.prompt_service import PromptService
    prompt = PromptService.get_prompt(
        prompt_name="dynamic_mapping",
        placeholders={"input_json": input_json}
    )
    return harden_prompt(prompt)
