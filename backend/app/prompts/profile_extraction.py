from __future__ import annotations
import json

PROMPT_VERSION = "1.0"


def build_profile_extraction_prompt(cv_text: str) -> str:
    """
    Builds a strict JSON-only prompt for Qwen to extract a DynamicCandidateProfile
    from CV text without any hardcoded assumptions.
    """
    structured_input = {
        "task_instructions": (
            "Act as an expert HR Profile Extraction Engine. "
            "Analyze the candidate_cv_markdown and extract a highly structured DynamicCandidateProfile. "
            "CRITICAL RULES: "
            "1. Do not hardcode any industry, role, degree, skill, or domain mapping. "
            "2. Dynamically derive the candidate's profile entirely from the provided CV evidence. "
            "3. Independently analyze: Education -> Experience -> Role Timeline -> Skills -> Projects -> Certifications -> Achievements. "
            "4. Prioritize recent and demonstrated professional capability over historical or unrelated background. "
            "5. Detect career or domain transitions automatically from chronological evidence. "
            "6. Never assume a candidate belongs to a domain based solely on a degree, title, or keyword without supporting evidence. "
            "7. If evidence is insufficient or conflicting, set confidence to 'UNCERTAIN' and explain in evidence_notes. "
            "8. Calculate relevant_experience_years logically by examining the timeline and durations of roles. "
            "9. Do not infer experience or skills not explicitly stated in the CV. "
            "10. For every extracted field, there must be corresponding evidence in the CV. If no evidence exists, omit the field or set it to empty. "
            "11. Never use generic terms like 'strong communication skills' unless the CV explicitly mentions them."
        ),
        "candidate_cv_markdown": cv_text[:7500],
    }

    input_json = json.dumps(structured_input, indent=2, ensure_ascii=False)

    from app.services.prompt_service import PromptService
    prompt = PromptService.get_prompt(
        prompt_name="profile_extraction",
        placeholders={"input_json": input_json}
    )
    return prompt
