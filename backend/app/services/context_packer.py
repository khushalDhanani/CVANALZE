from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.llm_input_security import sanitize_untrusted_text, wrap_untrusted_data
from app.services.quality_metrics import QualityMetrics

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[^\s]", re.UNICODE)
_HEADING_PATTERN = re.compile(
    r"^\s*(?:#{1,6}\s*)?(summary|profile|objective|experience|employment|work history|skills?|education|qualifications?|certifications?|projects?|achievements?|languages?)\s*:?[\s#]*$",
    re.IGNORECASE,
)
_PRIORITY = {"experience": 0, "employment": 0, "work history": 0, "skills": 1, "skill": 1, "education": 2, "qualification": 2, "qualifications": 2, "certification": 3, "certifications": 3, "summary": 4, "profile": 4, "objective": 4, "projects": 5, "project": 5, "achievements": 6, "achievement": 6, "languages": 7, "header": 8, "other": 9}


@dataclass(frozen=True)
class PackedContext:
    text: str
    estimated_tokens: int
    original_tokens: int
    omitted_sections: list[str] = field(default_factory=list)
    source_ranges: list[tuple[int, int]] = field(default_factory=list)
    injection_detected: bool = False
    redactions: int = 0


def estimate_tokens(value: str) -> int:
    return len(_TOKEN_PATTERN.findall(value or ""))


def _truncate_tokens(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    matches = list(_TOKEN_PATTERN.finditer(value))
    if len(matches) <= limit:
        return value
    return value[: matches[limit - 1].end()].rstrip()


def pack_cv_context(cv_text: str, *, max_tokens: int, deidentify: bool) -> PackedContext:
    sanitized = sanitize_untrusted_text(cv_text, deidentify=deidentify)
    text = sanitized.text
    original_tokens = estimate_tokens(text)
    budget = max(64, max_tokens)
    if original_tokens <= budget:
        return PackedContext(
            text=wrap_untrusted_data(text, "cv"),
            estimated_tokens=original_tokens,
            original_tokens=original_tokens,
            source_ranges=[(0, len(text))],
            injection_detected=sanitized.injection_detected,
            redactions=sanitized.redactions,
        )

    sections: list[tuple[str, str, int, int]] = []
    current_name = "header"
    current_start = 0
    current_lines: list[str] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        heading = _HEADING_PATTERN.match(line.strip())
        if heading and current_lines:
            sections.append((current_name, "".join(current_lines).strip(), current_start, offset))
            current_name = heading.group(1).lower()
            current_start = offset
            current_lines = [line]
        else:
            current_lines.append(line)
        offset += len(line)
    if current_lines:
        sections.append((current_name, "".join(current_lines).strip(), current_start, len(text)))

    ranked = sorted(enumerate(sections), key=lambda item: (_PRIORITY.get(item[1][0], _PRIORITY["other"]), item[0]))
    selected: list[tuple[int, str, str, int, int]] = []
    omitted: list[str] = []
    remaining = budget
    minimum_share = max(32, budget // max(1, len(sections) * 2))
    for original_index, (name, content, start, end) in ranked:
        content_tokens = estimate_tokens(content)
        structural_tokens = estimate_tokens(f"[{name.upper()}]\n") + (3 if selected else 0)
        if remaining <= structural_tokens:
            omitted.append(name)
            continue
        content_budget = remaining - structural_tokens
        allowance = min(content_tokens, max(minimum_share, content_budget // max(1, len(ranked) - len(selected))))
        chunk = _truncate_tokens(content, min(allowance, content_budget))
        if chunk:
            selected.append((original_index, name, chunk, start, end))
            remaining -= estimate_tokens(chunk) + structural_tokens
        if estimate_tokens(chunk) < content_tokens:
            omitted.append(name)

    selected.sort(key=lambda item: item[0])
    packed = "\n\n---\n\n".join(f"[{name.upper()}]\n{chunk}" for _, name, chunk, _, _ in selected)
    packed_tokens = estimate_tokens(packed)
    QualityMetrics.record("context", original_tokens=original_tokens, packed_tokens=packed_tokens, omitted_sections=len(omitted))
    return PackedContext(
        text=wrap_untrusted_data(packed, "cv"),
        estimated_tokens=packed_tokens,
        original_tokens=original_tokens,
        omitted_sections=sorted(set(omitted)),
        source_ranges=[(start, end) for _, _, _, start, end in selected],
        injection_detected=sanitized.injection_detected,
        redactions=sanitized.redactions,
    )
