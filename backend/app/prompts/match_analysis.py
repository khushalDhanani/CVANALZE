import json
from typing import Any

PROMPT_VERSION = "1.0"


def build_cv_job_prompt(cv_text: str, job: dict[str, Any]) -> str:
    """
    Builds a strict JSON-only prompt for Qwen to analyze a CV against job requirements.
    Provides structured JSON input instead of string concatenation to optimize Qwen's contextual understanding.
    """
    job_title = job.get("title", "Unknown Title")
    req_skills = job.get("required_skills", [])
    pref_keywords = job.get("preferred_keywords", [])

    structured_input = {
        "task_instructions": (
            "You are an expert HR recruitment assistant. "
            "Analyze the candidate_cv_markdown against the job_requirements. "
            "Your task is to identify matching skills, infer related skills (e.g., if they know React, they know JavaScript), "
            "and identify missing critical requirements."
        ),
        "job_requirements": {
            "job_title": job_title,
            "required_skills": req_skills,
            "preferred_keywords": pref_keywords,
        },
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
  "skill_matches": ["skill1", "skill2"],
  "inferred_skills": ["inferred1", "inferred2"],
  "missing_critical": ["missing1"],
  "semantic_reason": "A brief explanation of why the candidate fits or lacks fit"
}}
"""
    return prompt
