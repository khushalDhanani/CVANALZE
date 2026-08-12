from __future__ import annotations
import datetime
from dateutil.relativedelta import relativedelta
from app.schemas.work_experience_calculation import WorkExperienceCalculationSummary, MergedInterval
from app.schemas.work_experience_extraction import WorkExperienceConfig, WorkExperienceRecord


class WorkExperienceCalculationService:
    @classmethod
    def calculate_experience(
        cls, records: list[WorkExperienceRecord], config: WorkExperienceConfig
    ) -> WorkExperienceCalculationSummary:
        included_records = [r for r in records if r.include_in_experience and r.start_date_normalized and r.calculation_end_date]
        
        gross_days = 0
        ft_days = 0
        pt_days = 0
        ct_days = 0
        temp_days = 0
        appr_days = 0
        int_days = 0
        free_days = 0
        se_days = 0

        # Intervals for unique calculation
        intervals = []

        for r in included_records:
            try:
                start = datetime.date.fromisoformat(r.start_date_normalized)
                end = datetime.date.fromisoformat(r.calculation_end_date)
                
                # inclusive date boundaries
                duration = (end - start).days + 1
                if duration < 0:
                    continue

                gross_days += duration
                intervals.append((start, end))

                if r.employment_type == "full_time":
                    ft_days += duration
                elif r.employment_type == "part_time":
                    pt_days += duration
                elif r.employment_type == "contract":
                    ct_days += duration
                elif r.employment_type == "temporary":
                    temp_days += duration
                elif r.employment_type == "apprenticeship":
                    appr_days += duration
                elif r.employment_type == "internship":
                    int_days += duration
                elif r.employment_type == "freelance":
                    free_days += duration
                elif r.employment_type == "self_employed":
                    se_days += duration
            except ValueError:
                continue

        merged_intervals = cls._merge_intervals(
            intervals,
            merge_overlapping=config.merge_overlapping_periods,
            merge_adjacent=config.merge_adjacent_intervals,
        )

        unique_days = sum(((m.end_date - m.start_date).days + 1 for m in merged_intervals), 0)

        # Calculate calendar duration over all merged intervals
        total_months = 0
        for m in merged_intervals:
            delta = relativedelta(m.end_date + datetime.timedelta(days=1), m.start_date)
            total_months += (delta.years * 12) + delta.months + (1 if delta.days >= 15 else 0)

        completed_years = total_months // 12
        remaining_months = total_months % 12
        
        display_str = f"{completed_years} years {remaining_months} months"

        merged_interval_schemas = [
            MergedInterval(
                start_date=m.start_date.isoformat(),
                end_date=m.end_date.isoformat(),
                duration_days=(m.end_date - m.start_date).days + 1
            ) for m in merged_intervals
        ]

        return WorkExperienceCalculationSummary(
            gross_experience_days=gross_days,
            unique_experience_days=unique_days,
            full_time_experience_days=ft_days,
            part_time_experience_days=pt_days,
            contract_experience_days=ct_days,
            temporary_experience_days=temp_days,
            apprenticeship_experience_days=appr_days,
            internship_experience_days=int_days,
            freelance_experience_days=free_days,
            self_employed_experience_days=se_days,
            completed_years=completed_years,
            remaining_months=remaining_months,
            remaining_days=0,
            experience_display=display_str,
            merged_intervals=merged_interval_schemas,
        )

    @staticmethod
    def _merge_intervals(
        intervals: list[tuple[datetime.date, datetime.date]],
        merge_overlapping: bool,
        merge_adjacent: bool,
    ):
        class _Interval:
            def __init__(self, start, end):
                self.start_date = start
                self.end_date = end

        if not intervals:
            return []

        sorted_intervals = sorted(intervals, key=lambda x: (x[0], x[1]))
        merged = [_Interval(sorted_intervals[0][0], sorted_intervals[0][1])]

        for current_start, current_end in sorted_intervals[1:]:
            last = merged[-1]
            
            # Check overlap
            is_overlap = current_start <= last.end_date
            # Check adjacent
            is_adjacent = current_start == last.end_date + datetime.timedelta(days=1)
            
            should_merge = False
            if merge_overlapping and is_overlap:
                should_merge = True
            elif merge_adjacent and is_adjacent:
                should_merge = True
                
            if should_merge:
                last.end_date = max(last.end_date, current_end)
            else:
                merged.append(_Interval(current_start, current_end))

        return merged
