from __future__ import annotations
from app.services.context_packer import pack_cv_context
from app.services.llm_input_security import harden_prompt

WORK_EXPERIENCE_PROMPT_VERSION = "1.0.0"

def build_work_experience_prompt(candidate_id: str, ocr_text: str) -> str:
    from app.services.prompt_service import PromptService
    prompt = PromptService.get_prompt(
        prompt_name="work_experience_extraction_v1",
        placeholders={
            "candidate_id": candidate_id,
            "ocr_text": pack_cv_context(ocr_text, max_tokens=1800, deidentify=False).text
        }
    )
    return harden_prompt(prompt)
