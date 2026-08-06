from __future__ import annotations
WORK_EXPERIENCE_PROMPT_VERSION = "1.0.0"

def build_work_experience_prompt(candidate_id: str, ocr_text: str) -> str:
    from app.services.prompt_service import PromptService
    return PromptService.get_prompt(
        prompt_name="work_experience_extraction_v1",
        placeholders={
            "candidate_id": candidate_id,
            "ocr_text": ocr_text
        }
    )
