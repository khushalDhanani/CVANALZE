from __future__ import annotations
import json
from app.core.config import settings

PROMPT_VERSION = "1.0"


def _build_section_aware_cv_text(cv_text: str, max_chars: int) -> str:
    """
    Constructs a budget-aware CV text representation for LLM prompt context.
    If full text is under max_chars, returns 100% full text.
    If total length exceeds max_chars, parses sections (by markdown headings or line blocks)
    and constructs a balanced payload containing evidence from ALL CV sections
    (Experience, Education, Skills, Certifications, Projects), regardless of page position.
    """
    if not cv_text or len(cv_text) <= max_chars:
        return cv_text

    import re

    # Parse sections by headings (# or ## or ###)
    lines = cv_text.splitlines()
    sections: list[dict[str, Any]] = []
    current_title = "HEADER"
    current_lines: list[str] = []

    for line in lines:
        if line.strip().startswith("#"):
            if current_lines:
                sections.append({"title": current_title, "content": "\n".join(current_lines).strip()})
            current_title = line.strip().lstrip("#").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append({"title": current_title, "content": "\n".join(current_lines).strip()})

    # Categorize sections
    categorized: dict[str, list[str]] = {
        "header": [],
        "experience": [],
        "education": [],
        "skills": [],
        "certifications": [],
        "projects": [],
        "other": [],
    }

    for sec in sections:
        t_lower = sec["title"].lower()
        text = sec["content"]
        if not text:
            continue
        if any(k in t_lower for k in ("experience", "employment", "history", "career", "work")):
            categorized["experience"].append(text)
        elif any(k in t_lower for k in ("education", "academic", "qualification")):
            categorized["education"].append(text)
        elif any(k in t_lower for k in ("skill", "technolog", "competenc", "tools")):
            categorized["skills"].append(text)
        elif any(k in t_lower for k in ("certifi", "license", "accreditation")):
            categorized["certifications"].append(text)
        elif any(k in t_lower for k in ("project", "portfolio")):
            categorized["projects"].append(text)
        elif sec["title"] == "HEADER" or any(k in t_lower for k in ("summary", "profile", "contact", "about")):
            categorized["header"].append(text)
        else:
            categorized["other"].append(text)

    # Allocate character budget proportionally
    budget = max_chars
    selected_parts: list[str] = []

    # Priority 1: Header/Contact/Summary (up to 1200 chars)
    header_text = "\n\n".join(categorized["header"])
    if header_text:
        chunk = header_text[:1200]
        selected_parts.append(chunk)
        budget -= len(chunk)

    # Priority 2: Education (up to 800 chars)
    edu_text = "\n\n".join(categorized["education"])
    if edu_text:
        chunk = edu_text[:800]
        selected_parts.append(chunk)
        budget -= len(chunk)

    # Priority 3: Skills & Certifications (up to 1000 chars)
    skills_cert_text = "\n\n".join(categorized["skills"] + categorized["certifications"])
    if skills_cert_text:
        chunk = skills_cert_text[:1000]
        selected_parts.append(chunk)
        budget -= len(chunk)

    # Priority 4: Projects (up to 600 chars)
    projects_text = "\n\n".join(categorized["projects"])
    if projects_text and budget > 500:
        chunk = projects_text[:600]
        selected_parts.append(chunk)
        budget -= len(chunk)

    # Priority 5: Work Experience (remainder of budget)
    exp_text = "\n\n".join(categorized["experience"])
    if exp_text and budget > 200:
        chunk = exp_text[:budget]
        selected_parts.append(chunk)
        budget -= len(chunk)

    # Priority 6: Other sections if budget remains
    other_text = "\n\n".join(categorized["other"])
    if other_text and budget > 200:
        chunk = other_text[:budget]
        selected_parts.append(chunk)

    result = "\n\n---\n\n".join(selected_parts)
    return result if result.strip() else cv_text[:max_chars]


def build_profile_extraction_prompt(cv_text: str) -> str:
    """
    Builds a strict JSON-only prompt for Qwen to extract a DynamicCandidateProfile
    from CV text without any hardcoded assumptions.
    Uses section-aware budget allocation so all sections across multi-page CVs
    (Experience, Education, Skills, Certifications) are included in the prompt context.
    """
    cv_payload = _build_section_aware_cv_text(cv_text, max_chars=settings.LLM_PROFILE_MAX_CHARS)

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
        # Section-aware payload (includes Experience, Education, Skills, Certifications from all pages)
        "candidate_cv_markdown": cv_payload,
    }

    input_json = json.dumps(structured_input, indent=2, ensure_ascii=False)

    from app.services.prompt_service import PromptService
    prompt = PromptService.get_prompt(
        prompt_name="profile_extraction",
        placeholders={"input_json": input_json}
    )
    return prompt

