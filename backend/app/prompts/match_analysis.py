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

    from app.services.prompt_service import PromptService
    prompt = PromptService.get_prompt(
        prompt_name="match_analysis",
        placeholders={"input_json": input_json}
    )
    return prompt
