import json
from typing import Any

PROMPT_VERSION = "2.0"


def build_dynamic_mapping_prompt(cv_text: str, active_vacancies: list[dict[str, Any]]) -> str:
    """
    Builds a strict JSON-only prompt for Qwen to dynamically map a CV against
    a list of available active DB vacancies.
    """

    simplified_vacancies = []
    for vac in active_vacancies:
        simplified_vacancies.append(
            {
                "vacancy_id": vac.get("vacancy_id"),
                "job_profile_id": vac.get("job_profile_id"),
                "company_id": vac.get("company_id"),
                "department_id": vac.get("department_id"),
                "location_id": vac.get("location_id"),
                "job_title": vac.get("title"),
                "department": vac.get("department"),
                "requirements": vac.get("required_skills", []),
                "skills": vac.get("preferred_keywords", []),
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
        "candidate_cv_markdown": cv_text,
    }

    input_json = json.dumps(structured_input, indent=2, ensure_ascii=False)

    prompt = f"""/think
{input_json}

Provide your analysis in the EXACT JSON format below.
DO NOT include any markdown formatting like ```json or ```.
DO NOT include any thinking tokens or explanations outside the JSON object.
Return ONLY valid JSON.

Expected JSON Schema:
{{
  "matched_vacancies": [
    {{
      "vacancy_id": 1334,
      "semantic_reason": "Candidate's experience and skills directly correspond to the requirements of the vacancy record.",
      "inferred_skills": ["relevant_skill_1", "relevant_skill_2"]
    }}
  ]
}}
"""
    return prompt
