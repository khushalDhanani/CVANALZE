import pytest
from pydantic import ValidationError

from app.core.rule_config_manager import ExtractionPolicy
from app.services.resume_field_extractor import ResumeFieldExtractor


def test_name_header_window_and_fallback_are_policy_driven(monkeypatch) -> None:
    default_result = ResumeFieldExtractor.extract_candidate_name(
        ["RESUME", "Ada Lovelace"], None, None, None
    )
    assert default_result[0] == "Ada Lovelace"

    policy = ExtractionPolicy(
        header_search_line_limit=1,
        unknown_candidate_name="Configured Unknown",
    )
    monkeypatch.setattr(
        ResumeFieldExtractor,
        "_policy",
        classmethod(lambda cls: policy),
    )

    configured_result = ResumeFieldExtractor.extract_candidate_name(
        ["RESUME", "Ada Lovelace"], None, None, None
    )
    assert configured_result[0] == "Configured Unknown"


def test_name_and_skill_limits_are_policy_driven(monkeypatch) -> None:
    policy = ExtractionPolicy(name_max_chars=8, skill_max_chars=5)
    monkeypatch.setattr(
        ResumeFieldExtractor,
        "_policy",
        classmethod(lambda cls: policy),
    )

    assert not ResumeFieldExtractor._is_valid_name("Ada Lovelace", None, None, None)
    assert ResumeFieldExtractor._is_junk_skill("Python")


def test_invalid_extraction_limits_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ExtractionPolicy(header_search_line_limit=0)
    with pytest.raises(ValidationError):
        ExtractionPolicy(name_denied_token_ratio=1.1)
