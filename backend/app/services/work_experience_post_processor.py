import re
import datetime
import calendar
from typing import Tuple, List, Optional
from dateutil.parser import parse as date_parse

from app.schemas.work_experience_llm import LLMWorkExperienceRecord
from app.schemas.work_experience_extraction import (
    WorkExperienceRecord,
    WorkExperienceConfig,
    DuplicateRecord,
)

ORDINAL_PATTERN = re.compile(r"\b(\d{1,2})\s*(st|nd|rd|th)\b", flags=re.IGNORECASE)


class WorkExperiencePostProcessor:
    @classmethod
    def process_records(
        cls,
        llm_records: List[LLMWorkExperienceRecord],
        config: WorkExperienceConfig,
        reference_date_str: str,
    ) -> Tuple[List[WorkExperienceRecord], List[DuplicateRecord]]:
        
        reference_date = datetime.date.fromisoformat(reference_date_str)
        processed = []
        
        for i, llm_record in enumerate(llm_records):
            record_id = f"EXP-{(i + 1):03d}"
            
            # Normalize ordinal spacing
            start_orig = ORDINAL_PATTERN.sub(r"\1", llm_record.start_date_original)
            end_orig = ORDINAL_PATTERN.sub(r"\1", llm_record.end_date_original)
            
            start_norm, start_prec, est_start = cls._normalize_date(
                start_orig, is_start=True, precision_override=llm_record.start_date_precision
            )
            
            if llm_record.is_current:
                end_norm = None
                calc_end = reference_date_str
                end_prec = "day"
                est_end = False
            else:
                end_norm, end_prec, est_end = cls._normalize_date(
                    end_orig, is_start=False, precision_override=llm_record.end_date_precision
                )
                calc_end = end_norm
                
            # Filter rule evaluation
            include_in_exp = True
            exclusion_reason = None
            
            if not getattr(config, f"include_{llm_record.employment_type}", False):
                include_in_exp = False
                exclusion_reason = f"EMPLOYMENT_TYPE_DISABLED_{llm_record.employment_type.upper()}"
            elif llm_record.confidence < config.minimum_record_confidence:
                include_in_exp = False
                exclusion_reason = "CONFIDENCE_BELOW_THRESHOLD"
            elif start_prec == "year":
                if config.year_only_start_policy == "exclude":
                    include_in_exp = False
                    exclusion_reason = "YEAR_ONLY_POLICY_EXCLUDE"
            elif not llm_record.is_current and end_prec == "year":
                if config.year_only_end_policy == "exclude":
                    include_in_exp = False
                    exclusion_reason = "YEAR_ONLY_POLICY_EXCLUDE"

            warnings = llm_record.warnings.copy()
            review_reasons = []

            # Validation logic
            if not start_norm:
                warnings.append("Missing start date")
                review_reasons.append("MISSING_START_DATE")
            else:
                try:
                    s_date = datetime.date.fromisoformat(start_norm)
                    if s_date > reference_date:
                        warnings.append("Start date is in the future relative to reference date")
                        review_reasons.append("FUTURE_START_DATE")
                    if calc_end:
                        e_date = datetime.date.fromisoformat(calc_end)
                        if s_date > e_date:
                            warnings.append("Start date is after end date")
                            review_reasons.append("INVALID_DATE_RANGE")
                except ValueError:
                    pass
            
            requires_review = (
                (llm_record.confidence < config.human_review_threshold) or
                bool(review_reasons) or
                (start_prec == "year" and config.year_only_start_policy == "manual_review") or
                (not llm_record.is_current and end_prec == "year" and config.year_only_end_policy == "manual_review")
            )
            
            if (start_prec == "year" and config.year_only_start_policy == "manual_review"):
                review_reasons.append("YEAR_ONLY_POLICY_REVIEW")
            if (not llm_record.is_current and end_prec == "year" and config.year_only_end_policy == "manual_review"):
                review_reasons.append("YEAR_ONLY_POLICY_REVIEW")

            processed.append(
                WorkExperienceRecord(
                    record_id=record_id,
                    original_text=llm_record.original_text,
                    job_title_original=llm_record.job_title_original,
                    job_title_normalized=llm_record.job_title_normalized,
                    company_name_original=llm_record.company_name_original,
                    company_name_normalized=llm_record.company_name_normalized,
                    location=llm_record.location,
                    employment_type=llm_record.employment_type,
                    start_date_original=llm_record.start_date_original,
                    start_date_normalized=start_norm,
                    start_date_precision=start_prec,
                    end_date_original=llm_record.end_date_original,
                    end_date_normalized=end_norm,
                    calculation_end_date=calc_end,
                    end_date_precision=end_prec,
                    is_current=llm_record.is_current,
                    estimated_start_date=est_start,
                    estimated_end_date=est_end,
                    include_in_experience=include_in_exp,
                    exclusion_reason=exclusion_reason,
                    confidence=llm_record.confidence,
                    requires_review=requires_review,
                    warnings=warnings,
                    review_reason_codes=review_reasons,
                )
            )

        final_records, duplicates = cls._detect_duplicates(processed)
        return final_records, duplicates

    @classmethod
    def _normalize_date(
        cls, date_str: str, is_start: bool, precision_override: str
    ) -> Tuple[Optional[str], str, bool]:
        if not date_str:
            return None, "unknown", False

        # basic normalization
        date_str = date_str.strip()
        
        # Check if year only
        if re.match(r"^(19|20)\d{2}$", date_str):
            if is_start:
                return f"{date_str}-01-01", "year", True
            else:
                return f"{date_str}-12-31", "year", True

        try:
            parsed = date_parse(date_str, fuzzy=True, default=datetime.datetime(2025, 1, 1))
            
            # Determine precision
            # If string contains only month and year e.g. "Aug 2025"
            has_day = bool(re.search(r"\b\d{1,2}(st|nd|rd|th|/|-|,|\b\s+|$)", date_str.replace(str(parsed.year), "")))
            
            if not has_day or precision_override == "month":
                est = True
                prec = "month"
                if is_start:
                    day = 1
                else:
                    day = calendar.monthrange(parsed.year, parsed.month)[1]
                return f"{parsed.year:04d}-{parsed.month:02d}-{day:02d}", prec, est
            else:
                return parsed.date().isoformat(), "day", False
                
        except (ValueError, OverflowError):
            return None, "unknown", False

    @classmethod
    def _detect_duplicates(
        cls, records: List[WorkExperienceRecord]
    ) -> Tuple[List[WorkExperienceRecord], List[DuplicateRecord]]:
        duplicates = []
        kept_records = []
        
        for record in records:
            is_dup = False
            for kept in kept_records:
                score = 0.0
                matches = []
                
                c1 = (record.company_name_normalized or "").strip().lower()
                c2 = (kept.company_name_normalized or "").strip().lower()
                if c1 and c2 and c1 == c2:
                    score += 0.40
                    matches.append("company_name")
                    
                t1 = (record.job_title_normalized or "").strip().lower()
                t2 = (kept.job_title_normalized or "").strip().lower()
                if t1 and t2 and t1 == t2:
                    score += 0.25
                    matches.append("job_title")
                    
                if record.start_date_normalized and kept.start_date_normalized and record.start_date_normalized == kept.start_date_normalized:
                    score += 0.20
                    matches.append("start_date")
                    
                if record.calculation_end_date and kept.calculation_end_date and record.calculation_end_date == kept.calculation_end_date:
                    score += 0.15
                    matches.append("end_date")
                    
                if score >= 0.90:
                    is_dup = True
                    duplicates.append(
                        DuplicateRecord(
                            kept_record_id=kept.record_id,
                            duplicate_record_id=record.record_id,
                            duplicate_score=score,
                            matching_fields=matches,
                            reason="OCR duplicate based on matching threshold"
                        )
                    )
                    break
                    
            if not is_dup:
                kept_records.append(record)
                
        return kept_records, duplicates
