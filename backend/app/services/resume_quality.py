import re
from typing import Any

from app.core.rule_config_manager import RuleConfigManager
from app.services.resume_field_extractor import ResumeFieldExtractor


class ResumeQualityMetrics:
    @classmethod
    def compute(
        cls,
        text: str,
        page_count: int,
        pdf_type: str,
        parser_used: str,
        ocr_applied: bool,
    ) -> dict[str, Any]:
        clean_text = text.strip()
        words = re.findall(r"\b[a-zA-Z0-9_+-]+\b", clean_text)
        resume_quality = RuleConfigManager.get_resume_quality_rules()
        text_lower = clean_text.lower()
        sections_detected = [name for name, pattern in RuleConfigManager.get_compiled_section_patterns().items() if pattern.search(text_lower)]

        core_sections = set(resume_quality.core_sections)
        section_score = len([section for section in sections_detected if section in core_sections]) * resume_quality.section_weight
        has_email = bool(re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", clean_text))
        has_phone = bool(
            re.search(
                r"(\+?\d{1,4}[\s.-]?)?\(?\d{3,5}\)?[\s.-]?\d{3,5}[\s.-]?\d{3,5}",
                clean_text,
            )
        )
        location, location_confidence = ResumeFieldExtractor.extract_location(clean_text.splitlines())
        has_location = bool(location and location_confidence >= resume_quality.location_acceptance_min_confidence)
        contact_weights = resume_quality.contact_weights
        contact_score = (
            (contact_weights.get("email", 0.10) if has_email else 0.0) + (contact_weights.get("phone", 0.10) if has_phone else 0.0) + (contact_weights.get("location", 0.05) if has_location else 0.0)
        )

        words_per_page = len(words) / max(page_count, 1)
        density_score = 0.05
        for tier in resume_quality.density_scores:
            if words_per_page >= tier.min_words_per_page:
                density_score = tier.score
                break

        return {
            "pages": page_count,
            "characters": len(clean_text),
            "words": len(words),
            "sections_detected": sections_detected,
            "sections_count": len(sections_detected),
            "completeness_score": round(min(1.0, section_score + contact_score + density_score), 2),
            "has_email": has_email,
            "has_phone": has_phone,
            "pdf_type": pdf_type,
            "parser_used": parser_used,
            "ocr_applied": ocr_applied,
        }


QualityMetricsCalculator = ResumeQualityMetrics
