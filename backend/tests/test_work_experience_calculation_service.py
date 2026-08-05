import pytest
from app.services.work_experience_calculation_service import WorkExperienceCalculationService
from app.schemas.work_experience_extraction import WorkExperienceRecord, WorkExperienceConfig

def test_overlapping_jobs_merged():
    records = [
        WorkExperienceRecord(
            record_id="EXP-001",
            original_text="",
            job_title_original="",
            job_title_normalized="",
            company_name_original="",
            company_name_normalized="",
            employment_type="full_time",
            start_date_original="",
            start_date_normalized="2020-01-01",
            start_date_precision="day",
            end_date_original="",
            end_date_normalized="2020-12-31",
            calculation_end_date="2020-12-31",
            end_date_precision="day",
            is_current=False,
            estimated_start_date=False,
            estimated_end_date=False,
            include_in_experience=True,
            confidence=1.0,
            requires_review=False
        ),
        WorkExperienceRecord(
            record_id="EXP-002",
            original_text="",
            job_title_original="",
            job_title_normalized="",
            company_name_original="",
            company_name_normalized="",
            employment_type="full_time",
            start_date_original="",
            start_date_normalized="2020-06-01",
            start_date_precision="day",
            end_date_original="",
            end_date_normalized="2021-05-31",
            calculation_end_date="2021-05-31",
            end_date_precision="day",
            is_current=False,
            estimated_start_date=False,
            estimated_end_date=False,
            include_in_experience=True,
            confidence=1.0,
            requires_review=False
        )
    ]
    config = WorkExperienceConfig(merge_overlapping_periods=True, merge_adjacent_intervals=True)
    summary = WorkExperienceCalculationService.calculate_experience(records, config)
    
    # 2020-01-01 to 2020-12-31 (366 days leap year) + 2020-06-01 to 2021-05-31 (365 days)
    assert summary.gross_experience_days == 731
    # Merged: 2020-01-01 to 2021-05-31 (366 + 151 = 517 days)
    assert summary.unique_experience_days == 517

def test_career_gaps_not_counted():
    records = [
        WorkExperienceRecord(
            record_id="EXP-001",
            original_text="",
            job_title_original="",
            job_title_normalized="",
            company_name_original="",
            company_name_normalized="",
            employment_type="full_time",
            start_date_original="",
            start_date_normalized="2020-01-01",
            start_date_precision="day",
            end_date_original="",
            end_date_normalized="2020-12-31",
            calculation_end_date="2020-12-31",
            end_date_precision="day",
            is_current=False,
            estimated_start_date=False,
            estimated_end_date=False,
            include_in_experience=True,
            confidence=1.0,
            requires_review=False
        ),
        WorkExperienceRecord(
            record_id="EXP-002",
            original_text="",
            job_title_original="",
            job_title_normalized="",
            company_name_original="",
            company_name_normalized="",
            employment_type="full_time",
            start_date_original="",
            start_date_normalized="2022-01-01",
            start_date_precision="day",
            end_date_original="",
            end_date_normalized="2022-12-31",
            calculation_end_date="2022-12-31",
            end_date_precision="day",
            is_current=False,
            estimated_start_date=False,
            estimated_end_date=False,
            include_in_experience=True,
            confidence=1.0,
            requires_review=False
        )
    ]
    config = WorkExperienceConfig(merge_overlapping_periods=True, merge_adjacent_intervals=True)
    summary = WorkExperienceCalculationService.calculate_experience(records, config)
    
    assert summary.unique_experience_days == 366 + 365
    assert len(summary.merged_intervals) == 2
