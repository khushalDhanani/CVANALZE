import pytest
from app.services.work_experience_post_processor import WorkExperiencePostProcessor
from app.schemas.work_experience_llm import LLMWorkExperienceRecord
from app.schemas.work_experience_extraction import WorkExperienceConfig

def test_month_year_normalization():
    records = [
        LLMWorkExperienceRecord(
            original_text="Aug 2025 - Nov 2025",
            start_date_original="Aug 2025",
            end_date_original="Nov 2025",
            is_current=False
        )
    ]
    config = WorkExperienceConfig()
    
    processed, duplicates = WorkExperiencePostProcessor.process_records(records, config, "2026-08-05")
    
    assert len(processed) == 1
    assert processed[0].start_date_normalized == "2025-08-01"
    assert processed[0].start_date_precision == "month"
    assert processed[0].end_date_normalized == "2025-11-30"
    assert processed[0].end_date_precision == "month"

def test_ordinal_normalization():
    records = [
        LLMWorkExperienceRecord(
            original_text="10 th February 2025",
            start_date_original="10 th February 2025",
            end_date_original="15st March 2025",
            is_current=False
        )
    ]
    config = WorkExperienceConfig()
    
    processed, duplicates = WorkExperiencePostProcessor.process_records(records, config, "2026-08-05")
    
    assert processed[0].start_date_normalized == "2025-02-10"
    assert processed[0].end_date_normalized == "2025-03-15"

def test_year_only_policy_manual_review():
    records = [
        LLMWorkExperienceRecord(
            original_text="2020 - 2022",
            start_date_original="2020",
            end_date_original="2022",
            is_current=False
        )
    ]
    config = WorkExperienceConfig(year_only_start_policy="manual_review", year_only_end_policy="manual_review")
    
    processed, duplicates = WorkExperiencePostProcessor.process_records(records, config, "2026-08-05")
    
    assert processed[0].start_date_normalized == "2020-01-01"
    assert processed[0].end_date_normalized == "2022-12-31"
    assert processed[0].requires_review is True
    assert "YEAR_ONLY_POLICY_REVIEW" in processed[0].review_reason_codes

def test_duplicate_ocr_records():
    records = [
        LLMWorkExperienceRecord(
            company_name_normalized="Acme Corp",
            job_title_normalized="Engineer",
            start_date_original="2020-01-01",
            end_date_original="2022-01-01",
        ),
        LLMWorkExperienceRecord(
            company_name_normalized="Acme Corp",
            job_title_normalized="Engineer",
            start_date_original="2020-01-01",
            end_date_original="2022-01-01",
        )
    ]
    config = WorkExperienceConfig()
    
    processed, duplicates = WorkExperiencePostProcessor.process_records(records, config, "2026-08-05")
    
    assert len(processed) == 1
    assert len(duplicates) == 1
    assert duplicates[0].duplicate_score > 0.90
