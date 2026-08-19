from __future__ import annotations
import json
import re
from typing import Any

from app.core.config import settings
from app.core.logging import logger
from app.core.rule_config_manager import RuleConfigManager
from app.prompts.match_analysis import build_job_requirements
from app.services.context_packer import estimate_tokens, pack_cv_context
from app.services.llm_input_security import harden_prompt, sanitize_string_list, sanitize_untrusted_text

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
    packed_context = pack_cv_context(
        _clean_cv_text(cv_text),
        max_tokens=settings.LLM_CONTEXT_CV_TOKEN_BUDGET,
        deidentify=settings.LLM_DEIDENTIFY_MATCHING_INPUTS,
    )
    cleaned_cv = packed_context.text

    compact_vacancies = []
    ordered_vacancies = sorted(filtered_vacancies, key=lambda vac: str(vac.get("vacancy_id") or vac.get("id") or ""))
    for vac in ordered_vacancies:
        vac_id = vac.get("vacancy_id") or vac.get("id")
        item = {
            "vacancy_id": vac_id,
            "title": sanitize_untrusted_text(str(vac.get("title") or vac.get("job_title") or "")).text,
            "department": sanitize_untrusted_text(str(vac.get("department_name") or vac.get("department") or "")).text,
        }
        if vac.get("required_skills"):
            item["required_skills"] = sanitize_string_list(vac.get("required_skills"))
        if vac.get("preferred_keywords"):
            item["preferred_keywords"] = sanitize_string_list(vac.get("preferred_keywords"))
        if vac.get("min_experience_years") is not None:
            item["min_exp"] = vac.get("min_experience_years")
        if vac.get("max_experience_years") is not None:
            item["max_exp"] = vac.get("max_experience_years")
        if vac.get("max_ctc") is not None:
            item["max_ctc"] = vac.get("max_ctc")
        item["required_skills_are_mandatory"] = bool(vac.get("required_skills_are_mandatory", True))
        education_requirement = vac.get("education_requirements") or vac.get("required_education") or vac.get("education")
        if education_requirement:
            education_values = education_requirement if isinstance(education_requirement, (list, tuple, set)) else [education_requirement]
            item["education_req"] = sanitize_string_list(education_values)
        if vac.get("certifications"):
            certification_values = vac["certifications"] if isinstance(vac["certifications"], (list, tuple, set)) else [vac["certifications"]]
            item["certifications"] = sanitize_string_list(certification_values)
        if vac.get("technologies"):
            item["technologies"] = sanitize_string_list(vac.get("technologies"))
        responsibility_values = vac.get("responsibilities") or []
        if responsibility_values:
            responsibility_values = responsibility_values if isinstance(responsibility_values, (list, tuple, set)) else [responsibility_values]
            item["responsibilities"] = sanitize_string_list(responsibility_values)
        vacancy_description = vac.get("job_description") or vac.get("description")
        if vacancy_description:
            sanitized_desc = sanitize_untrusted_text(str(vacancy_description)).text.strip()
            if sanitized_desc:
                item["description"] = sanitized_desc[:400].rstrip() if len(sanitized_desc) > 400 else sanitized_desc
        item["requirements"] = build_job_requirements(vac)

        compact_vacancies.append(item)

    # Dynamic admission control: ensure prompt token budget never exceeds model context window headroom minus predict budget and safety buffer
    safety_buffer = 512
    max_prompt_token_budget = max(1000, settings.OLLAMA_OPTIMIZED_NUM_CTX - settings.OLLAMA_OPTIMIZED_NUM_PREDICT - safety_buffer)
    while len(compact_vacancies) > 1:
        trial_input = {
            "task": "Extract candidate profile, classify vacancy requirements, extract dual evidence, and analyze semantic fit.",
            "candidate_cv_text": cleaned_cv,
            "candidate_vacancies": compact_vacancies,
        }
        trial_json = json.dumps(trial_input, separators=(",", ":"), ensure_ascii=False)
        trial_tokens = estimate_tokens(trial_json) + 600
        if trial_tokens <= max_prompt_token_budget:
            break
        pruned = compact_vacancies.pop()
        logger.info(
            f"[ADMISSION_CONTROL] Pruned vacancy {pruned.get('vacancy_id')} to respect token budget "
            f"(trial_tokens={trial_tokens} budget={max_prompt_token_budget})."
        )

    structured_input = {
        "task": "Extract candidate profile, classify vacancy requirements, extract dual evidence, and analyze semantic fit.",
        "candidate_cv_text": cleaned_cv,
        "candidate_vacancies": compact_vacancies,
    }

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

    prompt = harden_prompt(prompt)
    char_count = len(prompt)
    token_estimate = max(1, estimate_tokens(prompt))

    return prompt, token_estimate, char_count
