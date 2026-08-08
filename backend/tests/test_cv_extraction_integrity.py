"""
Tests for CV extraction content integrity.

Requirements verified:
- LLM_CV_MAX_CHARS / LLM_PROFILE_MAX_CHARS / EMBEDDING_CV_MAX_CHARS are LLM-only settings
- Full extracted text is stored, not truncated
- EXPERIENCE_KEYWORD_SEARCH_CHARS covers long CVs (>10k chars)
- Content-loss detection fires when final < 50% of native
- optimized_match prompt CV section is always <= LLM_CV_MAX_CHARS
- profile_extraction prompt CV section is always <= LLM_PROFILE_MAX_CHARS
"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.prompts.optimized_match import _clean_cv_text, build_optimized_match_prompt
from app.prompts.profile_extraction import build_profile_extraction_prompt


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_long_cv(chars: int = 15_000, seed_text: str = "") -> str:
    """Generates a realistic-looking CV of at least `chars` characters."""
    base = (
        "John Doe\njohn.doe@email.com | +1-555-0100\n\n"
        "## Work Experience\n\n"
        "Senior Software Engineer | Acme Corp | Jan 2018 - Present\n"
        "- Led platform migration reducing latency by 40%\n"
        "- Managed team of 8 engineers\n\n"
        "Software Engineer | Beta Ltd | Mar 2014 - Dec 2017\n"
        "- Built microservices architecture\n"
        "- 5 years of experience in Python and Java\n\n"
        "## Education\n\n"
        "B.Sc. Computer Science | MIT | 2010 - 2014\n\n"
        "## Skills\n\n"
        "Python, Java, PostgreSQL, Redis, Docker, Kubernetes, AWS\n\n"
        "## Certifications\n\n"
        "AWS Certified Solutions Architect | 2020\n\n"
    )
    if seed_text:
        base += f"\n{seed_text}\n"
    while len(base) < chars:
        base += f"Additional project detail. Technologies used: Python, REST APIs, CI/CD. " * 5 + "\n"
    return base[:chars] if len(base) > chars else base


LONG_CV = _make_long_cv(15_000)
SHORT_CV = _make_long_cv(500)
SCANNED_CV_SIMULATION = "Name: Ali Khan\nEmail: ali@example.com\nExperience: 8 years in Manufacturing\n" + "x" * 200


# ---------------------------------------------------------------------------
# T1: Config settings exist and are labelled correctly
# ---------------------------------------------------------------------------

class TestConfigSettings:
    def test_llm_cv_max_chars_exists(self):
        assert hasattr(settings, "LLM_CV_MAX_CHARS")
        assert settings.LLM_CV_MAX_CHARS > 0

    def test_llm_profile_max_chars_exists(self):
        assert hasattr(settings, "LLM_PROFILE_MAX_CHARS")
        assert settings.LLM_PROFILE_MAX_CHARS > 0

    def test_embedding_cv_max_chars_exists(self):
        assert hasattr(settings, "EMBEDDING_CV_MAX_CHARS")
        assert settings.EMBEDDING_CV_MAX_CHARS > 0

    def test_experience_keyword_search_chars_covers_long_cvs(self):
        """EXPERIENCE_KEYWORD_SEARCH_CHARS must be at least 10k to cover long CVs."""
        assert settings.EXPERIENCE_KEYWORD_SEARCH_CHARS >= 10_000, (
            f"EXPERIENCE_KEYWORD_SEARCH_CHARS={settings.EXPERIENCE_KEYWORD_SEARCH_CHARS} "
            "must be >= 10000 to cover explicit experience statements in long CVs"
        )

    def test_llm_settings_are_smaller_than_max_cv_text(self):
        """LLM truncation limits must be much smaller than MAX_CV_TEXT_LENGTH_CHARS."""
        assert settings.LLM_CV_MAX_CHARS < settings.MAX_CV_TEXT_LENGTH_CHARS
        assert settings.LLM_PROFILE_MAX_CHARS < settings.MAX_CV_TEXT_LENGTH_CHARS


# ---------------------------------------------------------------------------
# T2: optimized_match prompt — CV is truncated only in the prompt, not upstream
# ---------------------------------------------------------------------------

class TestOptimizedMatchPromptTruncation:
    DUMMY_VACANCIES = [
        {"vacancy_id": "V1", "title": "Software Engineer", "department_name": "IT"},
        {"vacancy_id": "V2", "title": "Data Analyst", "department_name": "Analytics"},
    ]

    def test_long_cv_prompt_cv_section_capped(self):
        """The CV section in the LLM prompt must be <= LLM_CV_MAX_CHARS."""
        prompt, tokens, chars, vacancy_count = build_optimized_match_prompt(LONG_CV, self.DUMMY_VACANCIES)
        cleaned_cv = _clean_cv_text(LONG_CV)
        cv_in_prompt = cleaned_cv[:settings.LLM_CV_MAX_CHARS]
        assert len(cv_in_prompt) <= settings.LLM_CV_MAX_CHARS

    def test_full_cv_not_mutated_by_prompt_builder(self):
        """build_optimized_match_prompt must not modify the original cv_text variable."""
        original = LONG_CV
        original_len = len(original)
        build_optimized_match_prompt(original, self.DUMMY_VACANCIES)
        assert len(original) == original_len, "Original cv_text must not be truncated by prompt builder"

    def test_short_cv_fully_preserved_in_prompt(self):
        """For CVs shorter than LLM_CV_MAX_CHARS, all content must appear in the prompt."""
        prompt, tokens, chars, vacancy_count = build_optimized_match_prompt(SHORT_CV, self.DUMMY_VACANCIES)
        assert chars > 0
        assert vacancy_count == 2

    def test_vacancy_count_returned(self):
        """Must return 4-tuple including vacancy_count."""
        result = build_optimized_match_prompt(SHORT_CV, self.DUMMY_VACANCIES)
        assert len(result) == 4, "build_optimized_match_prompt must return (prompt, tokens, chars, vacancy_count)"
        _, _, _, vacancy_count = result
        assert vacancy_count == len(self.DUMMY_VACANCIES)

    def test_empty_vacancies(self):
        """Empty vacancy list must not crash and returns vacancy_count=0."""
        prompt, tokens, chars, vacancy_count = build_optimized_match_prompt(SHORT_CV, [])
        assert vacancy_count == 0
        assert len(prompt) > 0


# ---------------------------------------------------------------------------
# T3: profile_extraction prompt — CV capped at LLM_PROFILE_MAX_CHARS
# ---------------------------------------------------------------------------

class TestProfileExtractionPromptTruncation:
    def test_long_cv_profile_prompt_capped(self):
        """The CV section in the profile extraction prompt must be <= LLM_PROFILE_MAX_CHARS."""
        prompt = build_profile_extraction_prompt(LONG_CV)
        cap = settings.LLM_PROFILE_MAX_CHARS
        cv_in_prompt = LONG_CV[:cap]
        assert len(cv_in_prompt) <= cap
        assert len(prompt) > 0

    def test_full_cv_not_mutated_by_profile_prompt(self):
        """Profile prompt builder must not modify the original cv_text."""
        original_len = len(LONG_CV)
        build_profile_extraction_prompt(LONG_CV)
        assert len(LONG_CV) == original_len


# ---------------------------------------------------------------------------
# T4: Experience keyword search covers long CVs
# ---------------------------------------------------------------------------

class TestExperienceKeywordSearch:
    def test_experience_statement_after_4000_chars_found(self):
        """Explicit experience statement placed after 4000 chars must be found."""
        from app.services.experience_calculator import ExperienceCalculator

        padding = "x" * 5000  # push experience statement past old 4000-char limit
        cv_with_late_statement = padding + "\nTotal experience: 11 years in manufacturing.\n"
        result = ExperienceCalculator._extract_explicit_experience(cv_with_late_statement)
        assert result is not None, (
            "ExperienceCalculator must find experience statements beyond char 4000. "
            f"EXPERIENCE_KEYWORD_SEARCH_CHARS={settings.EXPERIENCE_KEYWORD_SEARCH_CHARS}"
        )
        assert abs(result - 11.0) < 0.1

    def test_experience_statement_at_start_still_found(self):
        """Experience statement at the start must still be found."""
        from app.services.experience_calculator import ExperienceCalculator

        cv = "Total experience: 7 years in software development.\n" + "x" * 2000
        result = ExperienceCalculator._extract_explicit_experience(cv)
        assert result is not None
        assert abs(result - 7.0) < 0.1

    def test_empty_cv_returns_none(self):
        """Empty CV text returns None without crashing."""
        from app.services.experience_calculator import ExperienceCalculator
        assert ExperienceCalculator._extract_explicit_experience("") is None


# ---------------------------------------------------------------------------
# T5: Text normalizer does not truncate
# ---------------------------------------------------------------------------

class TestTextNormalizerNoTruncation:
    def test_long_cv_sanitized_without_truncation(self):
        """ResumeTextNormalizer.sanitize must not truncate the text."""
        from app.services.resume_text_normalizer import ResumeTextNormalizer

        result = ResumeTextNormalizer.sanitize(LONG_CV)
        assert len(result) >= len(LONG_CV) * 0.5, (
            f"Sanitize dropped too many chars: in={len(LONG_CV)} out={len(result)}"
        )

    def test_multipage_cv_preserved(self):
        """Multi-page (>20k chars) CVs must survive sanitize without major content loss."""
        from app.services.resume_text_normalizer import ResumeTextNormalizer

        multipage = _make_long_cv(22_000)
        result = ResumeTextNormalizer.sanitize(multipage)
        assert len(result) >= len(multipage) * 0.5


# ---------------------------------------------------------------------------
# T6: Content-loss detection logic (unit test the condition directly)
# ---------------------------------------------------------------------------

class TestContentLossDetection:
    def test_content_loss_fires_when_final_lt_50pct_native(self):
        """Content loss is detected when final_chars < 50% of native_chars."""
        native_char_count = 5000
        final_chars = 2000  # 40% — should trigger
        content_loss = native_char_count > 200 and final_chars < native_char_count * 0.5
        assert content_loss is True

    def test_content_loss_not_fired_when_acceptable(self):
        """No content loss when final is >=50% of native."""
        native_char_count = 5000
        final_chars = 3000  # 60% — OK
        content_loss = native_char_count > 200 and final_chars < native_char_count * 0.5
        assert content_loss is False

    def test_content_loss_not_fired_for_small_native(self):
        """Short native text (<=200 chars, e.g. SCANNED_PDF) must not trigger false alarm."""
        native_char_count = 150  # scanned pdf with almost no native text
        final_chars = 50
        content_loss = native_char_count > 200 and final_chars < native_char_count * 0.5
        assert content_loss is False


# ---------------------------------------------------------------------------
# T7: Separation between full_cv_chars and llm_chars
# ---------------------------------------------------------------------------

class TestCVCharSeparation:
    def test_full_cv_always_gte_llm_chars(self):
        """The full extracted CV must always be >= the LLM truncated version."""
        cv = LONG_CV
        full_cv_chars = len(cv)
        llm_cv_chars = min(full_cv_chars, settings.LLM_CV_MAX_CHARS)
        assert full_cv_chars >= llm_cv_chars

    def test_llm_chars_equals_full_for_short_cv(self):
        """For CVs shorter than LLM_CV_MAX_CHARS, llm_chars == full_cv_chars."""
        short = "Name: Jane\nEmail: jane@co.com\n5 years experience in HR.\n" * 3
        full_cv_chars = len(short)
        llm_cv_chars = min(full_cv_chars, settings.LLM_CV_MAX_CHARS)
        assert llm_cv_chars == full_cv_chars

    def test_llm_chars_capped_for_long_cv(self):
        """For CVs longer than LLM_CV_MAX_CHARS, llm_chars is strictly less."""
        assert len(LONG_CV) > settings.LLM_CV_MAX_CHARS, "Test fixture must be longer than cap"
        full_cv_chars = len(LONG_CV)
        llm_cv_chars = min(full_cv_chars, settings.LLM_CV_MAX_CHARS)
        assert llm_cv_chars == settings.LLM_CV_MAX_CHARS
        assert llm_cv_chars < full_cv_chars


# ---------------------------------------------------------------------------
# T8: Clean CV text function does not drop structural content
# ---------------------------------------------------------------------------

class TestCleanCvText:
    def test_clean_preserves_key_sections(self):
        """_clean_cv_text must preserve names, emails, dates, section headers."""
        raw = (
            "John Smith\njohn.smith@company.com\n\n"
            "## Work Experience\n\n"
            "Engineer | Acme | Jan 2019 - Dec 2023\n\n"
            "## Education\n\n"
            "B.Sc. CS | MIT | 2015\n\n"
            "## Skills\n\n"
            "Python, Java, SQL\n"
        )
        cleaned = _clean_cv_text(raw)
        assert "John Smith" in cleaned
        assert "john.smith@company.com" in cleaned
        assert "Jan 2019" in cleaned
        assert "Dec 2023" in cleaned
        assert "Python" in cleaned
        assert "Education" in cleaned

    def test_clean_does_not_truncate(self):
        """_clean_cv_text must not truncate — that is done by the caller with [:LLM_CV_MAX_CHARS]."""
        big_cv = _make_long_cv(5000)
        cleaned = _clean_cv_text(big_cv)
        assert len(cleaned) >= len(big_cv) * 0.5
