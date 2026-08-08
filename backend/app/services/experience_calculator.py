from __future__ import annotations
import calendar
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from app.core.config import settings
from app.core.logging import logger
from app.services.date_interval_parser import DateIntervalParser


class ExperienceState:
    CALCULATED = "CALCULATED"
    CLAIMED = "CLAIMED"
    UNKNOWN = "UNKNOWN"
    ZERO_CONFIRMED = "ZERO_CONFIRMED"


class ExperienceCalculator:
    """
    One single centralized, canonical experience calculation engine.
    Guarantees deterministic calculation, date interval merging, present role handling,
    explicit CV claim fallback, non-zero guardrails for documented roles, and
    the four canonical states: CALCULATED, CLAIMED, UNKNOWN, ZERO_CONFIRMED.
    """

    @classmethod
    def _parse_date(cls, date_str: str, is_end_date: bool = False, ref_date: datetime | None = None) -> datetime | None:
        dt, _ = DateIntervalParser.parse_date_point(date_str, is_end_date=is_end_date, ref_date=ref_date)
        return dt

    @classmethod
    def _extract_date_range(cls, dates_str: str, ref_date: datetime | None = None) -> tuple[datetime | None, datetime | None]:
        target_ref = ref_date or datetime.now()
        interval = DateIntervalParser.parse_interval(dates_str, ref_date=target_ref)
        start = datetime.fromisoformat(interval.start_date) if interval.start_date else None
        end = datetime.fromisoformat(interval.end_date) if interval.end_date else (target_ref if interval.is_current else None)
        return start, end

    @classmethod
    def calculate_canonical_experience(
        cls,
        resume_json: dict[str, Any],
        cv_text: str = "",
        candidate_id: str = "",
        reference_date: datetime | None = None,
    ) -> dict[str, Any]:
        """
        One single canonical, authoritative experience calculator.
        Guarantees deterministic calculation, date interval merging, present role handling,
        unparsed date logging, and non-zero fallback for documented roles.
        """
        target_ref = reference_date or datetime.now()

        work_exp = (
            resume_json.get("work_experience")
            or resume_json.get("experience")
            or (resume_json.get("normalized") or {}).get("employment")
            or []
        )

        # Fallback inline extraction if work_exp is empty, resume_json is empty, and cv_text is provided
        if not work_exp and not resume_json and cv_text:
            from app.services.resume_field_extractor import ResumeFieldExtractor
            work_exp = ResumeFieldExtractor._extract_employment(cv_text.splitlines())

        valid_intervals: list[tuple[datetime, datetime]] = []
        unparsed_dates: list[dict[str, Any]] = []
        normalized_employment: list[dict[str, Any]] = []

        for idx, job in enumerate(work_exp, start=1):
            raw_dates = None
            job_title = None
            company = None
            responsibilities = []

            if isinstance(job, dict):
                raw_dates = job.get("dates") or (job.get("interval") or {}).get("raw_value")
                job_title = job.get("job_title") or (job.get("job_title") or {}).get("normalized_value")
                company = job.get("company") or (job.get("company") or {}).get("normalized_value") or job.get("company_name")
                responsibilities = job.get("responsibilities") or []
                if not raw_dates and job.get("start_date"):
                    raw_dates = f"{job.get('start_date')} - {job.get('end_date') or 'Present'}"
            elif isinstance(job, str):
                job_title = job

            start_date, end_date = None, None
            if raw_dates and isinstance(raw_dates, str):
                start_date, end_date = cls._extract_date_range(raw_dates, ref_date=target_ref)

            # Fallback inline search in title/company/description if raw_dates was missing
            if not start_date and isinstance(job, dict):
                for field in (job.get("job_title"), job.get("company"), job.get("description")):
                    if field and isinstance(field, str) and re.search(r"\b(19\d{2}|20\d{2}|present|current|now|ongoing|till date)\b", field, re.IGNORECASE):
                        s_d, e_d = cls._extract_date_range(field, ref_date=target_ref)
                        if s_d:
                            start_date, end_date = s_d, e_d
                            raw_dates = field
                            break

            # Handle present/current roles
            is_current = False
            if raw_dates and DateIntervalParser.is_present(str(raw_dates)):
                is_current = True
                end_date = target_ref
            elif start_date and not end_date:
                is_current = True
                end_date = target_ref

            if raw_dates and not start_date:
                logger.warning(
                    f"[EXPERIENCE_DATE_PARSE_UNSUPPORTED] Candidate '{candidate_id or 'unknown'}', Role #{idx} ('{job_title or company or 'Role'}'): Unable to parse raw date string '{raw_dates}'"
                )
                unparsed_dates.append({"role_index": idx, "raw_dates": raw_dates, "job_title": job_title})

            duration_months = None
            if start_date and end_date:
                if end_date < start_date:
                    end_date = start_date
                end_date = min(end_date, target_ref + timedelta(days=30))
                valid_intervals.append((start_date, end_date))
                duration_months = cls.interval_duration_months(start_date, end_date)

            clean_company = str(company).strip() if company else "Organization"
            clean_title = str(job_title).strip() if job_title else "Position"

            normalized_employment.append(
                {
                    "company": clean_company,
                    "role": clean_title,
                    "job_title": clean_title,
                    "dates": raw_dates or "N/A",
                    "start_date": start_date.date().isoformat() if start_date else None,
                    "end_date": end_date.date().isoformat() if end_date and not is_current else (None if is_current else None),
                    "is_current": is_current,
                    "duration_months": duration_months,
                    "extraction_confidence": 0.95 if start_date else 0.40,
                }
            )

        merged_intervals = cls._merge_intervals(valid_intervals)
        total_days = sum((end - start).days + 1 for start, end in merged_intervals)
        deterministic_years = round(total_days / 365.25, 1) if merged_intervals else None

        stated_years = cls._extract_explicit_experience(cv_text)

        quality_exp = float(resume_json.get("experience_years") or (resume_json.get("quality_metrics") or {}).get("experience_years") or 0.0)

        from app.services.experience_gap_service import ExperienceGapService
        gap_analysis = ExperienceGapService.analyze_timeline(resume_json, cv_text, reference_date=target_ref.date() if isinstance(target_ref, datetime) else target_ref)

        canonical_timeline_years = float(gap_analysis.summary.total_verified_years) if gap_analysis and gap_analysis.summary else 0.0

        # Determine Canonical State and Authoritative Duration
        if deterministic_years is not None and deterministic_years > 0:
            authoritative_years: float | None = deterministic_years
            experience_state = ExperienceState.CALCULATED
            total_months: int | None = int(round(authoritative_years * 12))
            years_part = total_months // 12
            months_part = total_months % 12
            gross_display = f"{years_part} years {months_part} months"
        elif canonical_timeline_years > 0:
            authoritative_years = canonical_timeline_years
            experience_state = ExperienceState.CALCULATED
            total_months = int(round(authoritative_years * 12))
            years_part = total_months // 12
            months_part = total_months % 12
            gross_display = f"{years_part} years {months_part} months"
        elif stated_years is not None and stated_years > 0:
            authoritative_years = stated_years
            experience_state = ExperienceState.CLAIMED
            total_months = int(round(authoritative_years * 12))
            years_part = total_months // 12
            months_part = total_months % 12
            gross_display = f"{years_part} years {months_part} months"
        elif quality_exp > 0:
            authoritative_years = quality_exp
            experience_state = ExperienceState.CALCULATED
            total_months = int(round(authoritative_years * 12))
            years_part = total_months // 12
            months_part = total_months % 12
            gross_display = f"{years_part} years {months_part} months"
        elif work_exp:
            # Documented history exists, but dates are unparseable and no stated claim was made.
            # MUST NEVER SILENTLY DEFAULT TO 0 YEARS 0 MONTHS.
            authoritative_years = None
            experience_state = ExperienceState.UNKNOWN
            total_months = None
            gross_display = "Experience Present (Dates Unparseable)"
        else:
            # Confirmed fresher / true zero experience
            authoritative_years = 0.0
            experience_state = ExperienceState.ZERO_CONFIRMED
            total_months = 0
            gross_display = "0 years 0 months"

        # Synchronize experience gap analysis summary so single source of truth canonical experience is reflected
        if gap_analysis and gap_analysis.summary:
            if authoritative_years is not None and authoritative_years > 0:
                gap_analysis.summary.total_verified_years = authoritative_years
                gap_analysis.summary.gross_display = gross_display
                if gap_analysis.summary.hr_observations:
                    gap_analysis.summary.hr_observations[0] = f"Total Employment Duration: {authoritative_years:.1f} years ({gross_display})."
            elif experience_state == ExperienceState.UNKNOWN:
                gap_analysis.summary.gross_display = gross_display
                if gap_analysis.summary.hr_observations:
                    gap_analysis.summary.hr_observations[0] = f"Employment History Documented: Dates require review ({len(work_exp)} roles)."

        gap_dict = gap_analysis.model_dump() if gap_analysis else {}

        # Seniority calculation based on canonical authoritative_years
        if authoritative_years is not None and authoritative_years >= 12.0:
            seniority = "Executive / Director"
        elif authoritative_years is not None and authoritative_years >= 8.0:
            seniority = "Lead / Principal"
        elif authoritative_years is not None and authoritative_years >= 5.0:
            seniority = "Senior"
        elif authoritative_years is not None and authoritative_years >= 2.0:
            seniority = "Mid-Level"
        elif authoritative_years is not None and authoritative_years >= 0.5:
            seniority = "Junior / Associate"
        elif work_exp:
            seniority = "Junior / Associate" if experience_state == ExperienceState.UNKNOWN else "Entry Level"
        else:
            seniority = "Entry Level"

        seniority_label = seniority if seniority.endswith("Level") else f"{seniority} level"

        if authoritative_years is not None and authoritative_years > 0:
            experience_assessment = f"Assessed as {seniority_label} with {authoritative_years:.1f} years of verified experience ({gross_display})."
        elif experience_state == ExperienceState.UNKNOWN:
            experience_assessment = f"Assessed as {seniority_label} with {len(work_exp)} documented employment role(s) (Dates unparseable)."
        elif work_exp:
            experience_assessment = f"Assessed as {seniority_label} based on {len(work_exp)} documented employment role(s)."
        else:
            experience_assessment = "Assessed as Entry Level (Confirmed zero professional experience / Fresher)."

        return {
            "experience_state": experience_state,
            "experience_years": authoritative_years,
            "total_experience_years": authoritative_years,
            "total_experience_months": total_months,
            "gross_display": gross_display,
            "deterministic_years": deterministic_years if deterministic_years is not None else (canonical_timeline_years if canonical_timeline_years > 0 else None),
            "stated_years": stated_years,
            "authoritative_years": authoritative_years,
            "seniority": seniority,
            "experience_assessment": experience_assessment,
            "validation_status": experience_state,
            "merged_intervals_count": len(merged_intervals),
            "unparsed_dates": unparsed_dates,
            "normalized_employment": normalized_employment,
            "gap_analysis": gap_dict,
        }

    @classmethod
    def calculate_total_experience(cls, resume_json: dict[str, Any], cv_text: str = "") -> float | None:
        """
        Calculates total experience using the canonical calculator.
        """
        summary = cls.calculate_canonical_experience(resume_json, cv_text)
        return summary["experience_years"]

    @classmethod
    def extract_intervals(cls, resume_json: dict[str, Any], ref_date: datetime | None = None) -> list[tuple[datetime, datetime]]:
        """Return valid employment intervals without applying stated or LLM experience."""
        target_ref = ref_date or datetime.now()
        intervals: list[tuple[datetime, datetime]] = []
        work_experience = resume_json.get("work_experience") or []
        for job in work_experience:
            dates_str = job.get("dates")

            start_date, end_date = None, None
            if dates_str:
                start_date, end_date = cls._extract_date_range(dates_str, ref_date=target_ref)

            # Fallback if dates were miscategorized by the parser
            if not start_date:
                fallback_fields = [
                    job.get("job_title"),
                    job.get("company"),
                    job.get("description"),
                ]
                for field in fallback_fields:
                    if field and isinstance(field, str):
                        if re.search(
                            r"\b(20\d{2}|19\d{2}|present|current|now|ongoing|till date)\b",
                            field,
                            re.IGNORECASE,
                        ):
                            s_date, e_date = cls._extract_date_range(field, ref_date=target_ref)
                            if s_date:
                                start_date, end_date = s_date, e_date
                                break

            # If missing end date but has start date, assume it's the current job
            if start_date and not end_date:
                end_date = target_ref

            if not start_date:
                continue

            end_date = max(end_date, start_date)
            end_date = min(end_date, target_ref + timedelta(days=30))

            if start_date and end_date:
                intervals.append((start_date, end_date))

        return intervals

    @staticmethod
    def interval_duration_months(start_date: datetime, end_date: datetime) -> int:
        if end_date < start_date:
            return 0
        months = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1
        return max(1, months)

    @classmethod
    def _merge_intervals(cls, intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
        if not intervals:
            return []
        intervals_sorted = sorted(intervals, key=lambda x: x[0])
        merged_intervals: list[tuple[datetime, datetime]] = []
        for interval in intervals_sorted:
            if not merged_intervals:
                merged_intervals.append(interval)
            else:
                last_start, last_end = merged_intervals[-1]
                current_start, current_end = interval

                if current_start <= last_end + timedelta(days=1):
                    # Overlap found, extend the last interval if necessary
                    merged_intervals[-1] = (last_start, max(last_end, current_end))
                else:
                    merged_intervals.append(interval)
        return merged_intervals

    @classmethod
    def _extract_explicit_experience(cls, cv_text: str) -> float | None:
        if not cv_text:
            return None

        # Scan 100% of full cv_text (no slicing). Note: explicit claims are fallback/validation ONLY
        # and never replace timeline-based calculation in calculate_canonical_experience.
        search_text = cv_text.lower()

        # Regex patterns covering "Work experience (6+ Years)", "Total experience: 5.5 years", "13+ years of experience", etc.
        patterns = [
            r"(?:work\s+)?(?:total\s+)?(?:experience|exp)\s*(?:[:\-\|]|\s|\()\s*(\d{1,2}(?:\.\d{1,2})?)\+?\s*(?:years?|yrs?)",
            r"(\d{1,2}(?:\.\d{1,2})?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:total\s+)?(?:experience|exp|in\b|expertise|field|working)",
            r"(?:with|having)\s+(\d{1,2}(?:\.\d{1,2})?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp|expertise)",
            r"(?:experience|expertise)\s*(?:of|[:\-\|]|\s|\()\s*(\d{1,2}(?:\.\d{1,2})?)\+?\s*(?:years?|yrs?)",
            r"(\d{1,2}(?:\.\d{1,2})?)\+?\s*(?:years?|yrs?)\s+(?:experienced|working)",
            r"(\d{1,2}(?:\.\d{1,2})?)\+?\s*(?:years?|yrs?)\s*(?:\)|\b)",
        ]

        for p in patterns:
            match = re.search(p, search_text)
            if match:
                try:
                    val = float(match.group(1))
                    if 0.1 <= val <= 50.0:
                        return val
                except ValueError:
                    continue
        return None
