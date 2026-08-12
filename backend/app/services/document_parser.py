from __future__ import annotations
"""Compatibility façade for CV document conversion and structured extraction.

Existing imports remain stable while focused implementations live in dedicated modules.
"""

from app.services.document_conversion import MarkdownGenerator, MarkdownResult
from app.services.resume_field_extractor import ResumeJsonExtractor
from app.services.resume_quality import QualityMetricsCalculator
from app.services.resume_text_normalizer import TextSanitizer

__all__ = [
    "MarkdownGenerator",
    "MarkdownResult",
    "QualityMetricsCalculator",
    "ResumeJsonExtractor",
    "TextSanitizer",
]
