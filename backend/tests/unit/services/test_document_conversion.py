from __future__ import annotations

from app.services.document_conversion import DocumentConversionService
from app.services.document_parser import ResumeJsonExtractor, TextSanitizer
from app.services.resume_text_normalizer import ResumeTextNormalizer


def test_resume_text_normalizer_unescapes_html() -> None:
    raw = "Senior React &amp; Python Developer &lt;Tech Lead&gt;"
    cleaned = ResumeTextNormalizer.sanitize(raw)
    assert "&amp;" not in cleaned
    assert "&lt;" not in cleaned
    assert "Senior React & Python Developer <Tech Lead>" in cleaned


def test_resume_text_normalizer_removes_comments_and_checkmarks() -> None:
    raw = "<!-- image -->\n- [x] Developed REST APIs <!-- hidden comment -->\n- [ ] Maintained databases"
    cleaned = ResumeTextNormalizer.sanitize(raw)
    assert "<!-- image -->" not in cleaned
    assert "hidden comment" not in cleaned
    assert "- [x]" not in cleaned
    assert "Developed REST APIs" in cleaned
    assert "Maintained databases" in cleaned


def test_resume_text_normalizer_deduplicates_consecutive_headings() -> None:
    raw = "## WORK EXPERIENCE\n## WORK EXPERIENCE\nSoftware Engineer at Acme Corp (2020-2023)"
    cleaned = ResumeTextNormalizer.sanitize(raw)
    count = cleaned.count("## WORK EXPERIENCE")
    assert count == 1


def test_document_parser_facade_compatibility() -> None:
    raw_cv = "Developer at Tech Corp &amp; Company"
    cleaned = TextSanitizer.sanitize(raw_cv)
    assert "&amp;" not in cleaned
    assert "Developer at Tech Corp & Company" in cleaned
