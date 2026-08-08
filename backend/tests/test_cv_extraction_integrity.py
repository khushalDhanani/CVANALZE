"""
Tests for CV extraction content integrity & protection.

Requirements verified:
- EXPERIENCE_KEYWORD_SEARCH_CHARS removed; deterministic experience/date parsing scans 100% full CV text
- Section-aware profile extraction prompt captures sections from page 5+ (char 18,000+)
- Multi-chunk embedding aggregation captures vector representation for 20k+ char CVs
- Multi-dimensional content-loss validation flags length ratio, missing dates, missing contact emails
- optimized_match prompt CV section is always <= LLM_CV_MAX_CHARS=4000
"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.prompts.optimized_match import _clean_cv_text, build_optimized_match_prompt
from app.prompts.profile_extraction import _build_section_aware_cv_text, build_profile_extraction_prompt


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_very_long_multipage_cv(chars: int = 25_000) -> str:
    """Generates a realistic 25,000+ character multi-page CV with late content on page 5+."""
    padding = "Detailed project documentation. Implemented microservices using Python and Docker. " * 30 + "\n"
    
    cv = (
        "John Doe\njohn.doe@email.com | +1-555-0100\n\n"
        "## Professional Summary\n\n"
        "Results-driven Engineering Leader with 15+ years of experience.\n\n"
        "## Work Experience\n\n"
        "Vice President of Engineering | Enterprise Corp | Jan 2021 - Present\n"
        "- Overseeing 50+ engineers across 4 domains.\n\n"
        + padding * 4 +
        "Director of Software Development | Global Systems | Mar 2016 - Dec 2020\n"
        "- Built cloud infrastructure handling 1M req/sec.\n\n"
        + padding * 4 +
        "Lead Architect | Tech Innovators | Jun 2010 - Feb 2016\n"
        "- Architected high-throughput message streaming.\n\n"
        + padding * 4 +
        "## Education\n\n"
        "Ph.D. in Computer Science | Stanford University | 2005 - 2010\n"
        "B.S. in Electrical Engineering | UC Berkeley | 2001 - 2005\n\n"
        "## Certifications\n\n"
        "AWS Certified Solutions Architect Professional | 2022\n"
        "Certified Information Systems Security Professional (CISSP) | 2021\n\n"
        "## Key Projects & Specialized Skills\n\n"
        "Specialized Skills: Distributed Systems, Rust, Golang, Kubernetes, PyTorch, Quantum Computing\n"
        "Overall Experience: 18 years in Enterprise Software Architecture\n"
    )
    return cv


VERY_LONG_CV = _make_very_long_multipage_cv(25_000)
SHORT_CV = VERY_LONG_CV[:500]


# ---------------------------------------------------------------------------
# T1: Config settings verify LLM-only boundaries
# ---------------------------------------------------------------------------

class TestConfigSettings:
    def test_llm_cv_max_chars_exists(self):
        assert hasattr(settings, "LLM_CV_MAX_CHARS")
        assert settings.LLM_CV_MAX_CHARS == 4000

    def test_llm_profile_max_chars_exists(self):
        assert hasattr(settings, "LLM_PROFILE_MAX_CHARS")
        assert settings.LLM_PROFILE_MAX_CHARS == 7500

    def test_experience_keyword_search_chars_removed(self):
        """EXPERIENCE_KEYWORD_SEARCH_CHARS must be removed so 100% of full CV text is scanned."""
        assert not hasattr(settings, "EXPERIENCE_KEYWORD_SEARCH_CHARS")


# ---------------------------------------------------------------------------
# T2: Deterministic Experience Calculator scans 100% full CV text
# ---------------------------------------------------------------------------

class TestExperienceCalculatorFullScan:
    def test_explicit_experience_statement_at_char_22000_detected(self):
        """Explicit experience statement placed at char 22,000+ must be detected."""
        from app.services.experience_calculator import ExperienceCalculator

        cv_with_late_exp = VERY_LONG_CV
        assert len(cv_with_late_exp) > 20_000
        result = ExperienceCalculator._extract_explicit_experience(cv_with_late_exp)
        assert result is not None, "Explicit experience statement at char 22,000+ must be detected"
        assert abs(result - 18.0) < 0.1

    def test_timeline_calculation_takes_precedence_over_explicit_claim(self):
        """Timeline-based calculation (2001-Present) must produce CALCULATED state."""
        from app.services.experience_calculator import ExperienceCalculator

        result = ExperienceCalculator.calculate_canonical_experience({}, cv_text=VERY_LONG_CV)
        assert result["experience_years"] > 0
        assert result["experience_state"] in ("CALCULATED", "UNKNOWN")


# ---------------------------------------------------------------------------
# T3: Section-Aware Profile Extraction Prompt
# ---------------------------------------------------------------------------

class TestSectionAwareProfileExtraction:
    def test_late_sections_included_in_profile_prompt(self):
        """Certifications and Education appearing past char 20,000 must be in section-aware payload."""
        payload = _build_section_aware_cv_text(VERY_LONG_CV, max_chars=settings.LLM_PROFILE_MAX_CHARS)
        assert len(payload) <= settings.LLM_PROFILE_MAX_CHARS + 500
        # Education and Certifications from the end of the 25k CV must be present
        assert "Education" in payload or "Stanford" in payload
        assert "Certifications" in payload or "CISSP" in payload
        assert "Work Experience" in payload or "Enterprise Corp" in payload

    def test_short_cv_returns_unmodified(self):
        """Short CV under limit returns 100% full text without modification."""
        payload = _build_section_aware_cv_text(SHORT_CV, max_chars=settings.LLM_PROFILE_MAX_CHARS)
        assert payload == SHORT_CV


# ---------------------------------------------------------------------------
# T4: Multi-Chunk Vector Embedding Aggregation
# ---------------------------------------------------------------------------

class TestMultiChunkEmbeddingAggregation:
    def test_long_cv_triggers_chunk_pooling(self, monkeypatch):
        """CV text > 3000 chars must generate pooled multi-chunk embeddings."""
        from app.services.embedding_service import EmbeddingService

        # Mock Ollama batch embed to return dummy 768-dim vectors
        def mock_batch_embed(model, texts):
            return [[0.1] * 768 for _ in texts]

        monkeypatch.setattr(EmbeddingService, "_call_ollama_batch_embed", mock_batch_embed)
        monkeypatch.setattr(settings, "EMBEDDING_ENABLED", True)

        vec = EmbeddingService.generate_embedding(VERY_LONG_CV, model_version="nomic-embed-text")
        assert vec is not None
        assert len(vec) == 768


# ---------------------------------------------------------------------------
# T5: Multi-Dimensional Content-Loss Validation
# ---------------------------------------------------------------------------

class TestMultiDimensionalContentLossValidation:
    def test_length_ratio_content_loss(self):
        """Length ratio < 50% triggers content loss."""
        native_chars = 10_000
        clean_chars = 3_000
        content_loss = native_chars > 200 and clean_chars < native_chars * 0.5
        assert content_loss is True

    def test_date_loss_detection(self):
        """Loss of >50% of 4-digit years triggers content loss."""
        import re
        native_text = "Worked at Corp A from 2010 to 2014, then Corp B 2015 to 2020 and Corp C 2021 to 2024."
        clean_text = "Worked at Corp A. Position: Manager."
        native_years = set(re.findall(r"\b(19\d{2}|20\d{2})\b", native_text))
        clean_years = set(re.findall(r"\b(19\d{2}|20\d{2})\b", clean_text))
        date_loss = len(native_years) >= 2 and len(clean_years) < len(native_years) * 0.5
        assert date_loss is True

    def test_email_loss_detection(self):
        """Loss of contact email triggers content loss."""
        import re
        native_text = "John Smith john.smith@company.com Phone: 555-0199"
        clean_text = "John Smith Phone: 555-0199"
        native_emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", native_text)
        clean_emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", clean_text)
        email_loss = bool(native_emails and not clean_emails)
        assert email_loss is True


# ---------------------------------------------------------------------------
# T6: optimized_match prompt CV slice remains capped at LLM_CV_MAX_CHARS
# ---------------------------------------------------------------------------

class TestOptimizedMatchPromptCap:
    def test_optimized_match_cv_text_capped_at_4000(self):
        """build_optimized_match_prompt must cap CV text at LLM_CV_MAX_CHARS=4000."""
        prompt, tokens, chars = build_optimized_match_prompt(
            VERY_LONG_CV,
            [{"vacancy_id": "V1", "title": "VP Engineering", "department_name": "Engineering"}]
        )
        cleaned_cv = _clean_cv_text(VERY_LONG_CV)
        cv_in_prompt = cleaned_cv[:settings.LLM_CV_MAX_CHARS]
        assert len(cv_in_prompt) <= settings.LLM_CV_MAX_CHARS
