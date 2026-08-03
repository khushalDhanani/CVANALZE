import re

from app.core.rule_config_manager import RuleConfigManager


class ResumeTextNormalizer:
    @classmethod
    def sanitize(cls, raw_text: str) -> str:
        if not raw_text:
            return ""

        text = re.sub(r"<!--\s*image\s*-->", "", raw_text)
        text = re.sub(r"<!--\s*.*?\s*-->", "", text, flags=re.DOTALL)
        text = re.sub(r"-\s*\[[x\s]\]\s*", "", text, flags=re.IGNORECASE)

        cleaned_lines = [cls._collapse_spaced_letters(line).rstrip() for line in text.splitlines()]
        text = "\n".join(cleaned_lines)

        for pattern, replacement in RuleConfigManager.get_compiled_heading_normalizations():
            text = pattern.sub(replacement, text)

        deduplicated_lines: list[str] = []
        last_heading: str | None = None
        for line in text.splitlines():
            clean_line = line.strip()
            if clean_line.startswith("## "):
                heading = clean_line.lower()
                if heading == last_heading:
                    continue
                last_heading = heading
            elif clean_line:
                last_heading = None
            deduplicated_lines.append(line)

        text = "\n".join(deduplicated_lines)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    @staticmethod
    def _collapse_spaced_letters(line: str) -> str:
        if not line.strip():
            return ""

        heading_match = re.match(r"^(\s*#+\s*)(.*)$", line)
        prefix = heading_match.group(1) if heading_match else ""
        content = heading_match.group(2) if heading_match else line
        fixed_parts: list[str] = []

        for part in re.split(r"\s{2,}", content.strip()):
            tokens = part.split()
            is_spaced_word = len(tokens) >= 3 and all(len(token) == 1 for token in tokens)
            is_short_spaced_word = len(tokens) >= 2 and all(len(token) == 1 for token in tokens) and len(part.replace(" ", "")) >= 3
            fixed_parts.append("".join(tokens) if is_spaced_word or is_short_spaced_word else part)

        normalized = " ".join(fixed_parts)
        return f"{prefix}{normalized}" if prefix else normalized


TextSanitizer = ResumeTextNormalizer

