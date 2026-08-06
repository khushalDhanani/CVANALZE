from __future__ import annotations
import json
import re
from typing import Any

from app.core.config import settings

PROMPT_VERSION = settings.OPTIMIZED_PROMPT_VERSION


def _clean_cv_text(cv_text: str) -> str:
    """
    Strips excessive blank lines and repetitive whitespace to compress prompt size
    without losing any text content, skills, experience, or certifications.
    """
    lines = [line.strip() for line in cv_text.splitlines() if line.strip()]
    cleaned = "\n".join(lines)
    # Replace 3 or more spaces with single space
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned


def build_optimized_match_prompt(cv_text: str, filtered_vacancies: list[dict[str, Any]]) -> tuple[str, int, int]:
    """
    Builds a single, compact JSON prompt for Qwen to extract candidate profile,
    classify vacancy requirements, extract dual evidence, and perform semantic evaluation.

    Returns: (prompt_str, estimated_token_count, char_count)
    """
    cleaned_cv = _clean_cv_text(cv_text)[:7500]

    compact_vacancies = []
    for vac in filtered_vacancies:
        vac_id = vac.get("vacancy_id") or vac.get("id")
        item = {
            "vacancy_id": vac_id,
            "title": vac.get("title") or vac.get("job_title"),
            "department": vac.get("department_name") or vac.get("department"),
        }
        if vac.get("required_skills"):
            item["required_skills"] = vac.get("required_skills")
        if vac.get("preferred_keywords"):
            item["preferred_keywords"] = vac.get("preferred_keywords")
        if vac.get("min_experience_years") is not None:
            item["min_exp"] = vac.get("min_experience_years")
        if vac.get("education_requirements"):
            item["education_req"] = vac.get("education_requirements")
        if vac.get("certifications"):
            item["certifications"] = vac.get("certifications")

        compact_vacancies.append(item)

    structured_input = {
        "task": "Extract candidate profile, classify vacancy requirements, extract dual evidence, and analyze semantic fit.",
        "candidate_cv_text": cleaned_cv,
        "candidate_vacancies": compact_vacancies,
    }

    from app.core.rule_config_manager import RuleConfigManager

    taxonomy = RuleConfigManager.get_taxonomy_rules()
    canonical_domains = taxonomy.canonical_domains
    domain_list_str = ", ".join(f'"{d}"' for d in canonical_domains)

    # Gather valid department names from the repository as an extra grounding signal
    try:
        from app.repositories.department_domain import department_domain_repository

        domains = department_domain_repository.get_all_domains()
        dept_names = [d.department_name for d in domains if d.is_active and d.department_name]
    except Exception:
        dept_names = []
    dept_list_str = ", ".join(f'"{d}"' for d in dept_names) if dept_names else "(see canonical_domains list)"

    input_json = json.dumps(structured_input, separators=(",", ":"), ensure_ascii=False)

    # Try to load prompt template from database
    from app.services.prompt_service import PromptService
    prompt = PromptService.get_prompt(
        prompt_name="optimized_match",
        placeholders={
            "input_json": input_json,
            "domain_list_str": domain_list_str,
            "dept_list_str": dept_list_str
        }
    )

    char_count = len(prompt)
    token_estimate = max(1, char_count // 4)

    return prompt, token_estimate, char_count
