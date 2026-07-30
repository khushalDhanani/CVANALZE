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


def build_optimized_match_prompt(
    cv_text: str, filtered_vacancies: list[dict[str, Any]]
) -> tuple[str, int, int]:
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

    input_json = json.dumps(structured_input, separators=(",", ":"), ensure_ascii=False)

    prompt = f"""{input_json}

EVIDENCE-BASED REASONING RULES:
1. Do NOT make assumptions or infer experience not explicitly supported by the CV.
2. EVERY conclusion in semantic_reason must reference specific evidence from the CV.
3. If evidence is missing for a requirement, state "No evidence found" — do not guess.
4. Do not use generic phrases like "strong experience" unless backed by specific skills, projects, or responsibilities cited from the CV.
5. Compare the candidate against each vacancy requirement item by item.
6. If there is a mismatch (department, domain, education, role, technology, skills), explicitly report it.
7. Never increase semantic_fit_score based on assumptions — score only on verified evidence.
8. If there is no genuine match with any active vacancy, set active_vacancy_summary to "No suitable active vacancy found.".

INSTRUCTIONS:
Return ONLY valid JSON matching the exact schema below without markdown wrapper, thinking tokens, or extra commentary.

Expected JSON Schema:
{{
  "candidate_profile": {{
    "core_skills": ["List of explicitly stated skills"],
    "inferred_skills": ["List of logical inferred skills, e.g. React implies JavaScript"],
    "relevant_experience_years": 5.0,
    "education_domains": ["Extracted education domains/degrees"],
    "certifications": ["Extracted certifications"],
    "current_role": "Current or most recent job title",
    "professional_domains": ["Extracted professional domain areas"],
    "recommended_department": "Most suitable department for candidate",
    "professional_domain": "Candidate's specialized professional domain",
    "strengths": ["Key candidate strengths from skills, experience, projects"],
    "suitable_job_roles": ["List of suitable market job roles"]
  }},
  "active_vacancy_summary": "Summary of genuine active vacancy match if genuine match exists; otherwise 'No suitable active vacancy found.'",
  "ai_career_summary": "Independent AI analysis of candidate's profile, strengths, recommended department, and suitable job roles.",
  "matched_vacancies": [
    {{
      "vacancy_id": 101,
      "semantic_reason": "Clear explanation of semantic fit based on CV evidence, citing specific skills, projects, or roles. If no fit, state 'No evidence found for X requirement'.",
      "inferred_skills": ["Inferred skills relevant to this specific vacancy"],
      "matched_skills": ["Skills from required_skills present in CV"],
      "missing_critical": ["Critical requirements missing"],
      "semantic_fit_score": 85.0,
      "career_transition_detected": false,
      "career_transition_note": "Optional notes if dynamic career transition detected",
      "classified_requirements": [
        {{
          "requirement_id": "req_1",
          "description": "Requirement description",
          "tier": "MANDATORY",
          "status": "SATISFIED",
          "failure_reason": null
        }}
      ],
      "evidence_snippets": {{
        "req_1": {{
          "cv_evidence": "Quote or verified fact from CV text",
          "vacancy_evidence": "Exact requirement text from vacancy"
        }}
      }}
    }}
  ]
}}
"""
    char_count = len(prompt)
    token_estimate = max(1, char_count // 4)

    return prompt, token_estimate, char_count

