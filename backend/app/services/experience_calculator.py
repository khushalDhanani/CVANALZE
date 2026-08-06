from __future__ import annotations
import re
from datetime import datetime
from typing import Any

from app.core.logging import logger


class ExperienceCalculator:
    """
    Deterministically calculates candidate experience based on extracted work history dates.
    Handles overlapping periods, gaps, and various date formats.
    """

    MONTH_MAP = {
        "jan": 1,
        "january": 1,
        "feb": 2,
        "february": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "sept": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
    }

    @classmethod
    def _parse_date(cls, date_str: str, is_end_date: bool = False) -> datetime | None:
        from app.services.date_interval_parser import DateIntervalParser
        dt, _ = DateIntervalParser.parse_date_point(date_str, is_end_date=is_end_date)
        return dt

    @classmethod
    def _extract_date_range(cls, dates_str: str) -> tuple[datetime | None, datetime | None]:
        from app.services.date_interval_parser import DateIntervalParser
        interval = DateIntervalParser.parse_interval(dates_str)
        start = datetime.fromisoformat(interval.start_date) if interval.start_date else None
        end = datetime.fromisoformat(interval.end_date) if interval.end_date else (datetime.now() if interval.is_current else None)
        return start, end

    @classmethod
    def calculate_canonical_experience(
        cls,
        resume_json: dict[str, Any],
        cv_text: str = "",
        candidate_id: str = "",
    ) -> dict[str, Any]:
        """
        One single canonical, authoritative experience calculator.
        Guarantees deterministic calculation, date interval merging, present role handling,
        unparsed date logging, and non-zero fallback for documented roles.
        """
        work_exp = (
            resume_json.get("work_experience")
            or resume_json.get("experience")
            or (resume_json.get("normalized") or {}).get("employment")
            or []
        )

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
            elif isinstance(job, str):
                job_title = job

            start_date, end_date = None, None
            if raw_dates and isinstance(raw_dates, str):
                start_date, end_date = cls._extract_date_range(raw_dates)

            # Fallback inline search in title/company/description if raw_dates was missing
            if not start_date and isinstance(job, dict):
                for field in (job.get("job_title"), job.get("company"), job.get("description")):
                    if field and isinstance(field, str) and re.search(r"\b(19\d{2}|20\d{2}|present|current|now)\b", field, re.IGNORECASE):
                        s_d, e_d = cls._extract_date_range(field)
                        if s_d:
                            start_date, end_date = s_d, e_d
                            raw_dates = field
                            break

            # Handle present/current roles
            is_current = False
            if raw_dates and re.search(r"\b(present|current|now|till date|onwards|till now|currently|presently)\b", str(raw_dates), re.IGNORECASE):
                is_current = True
                end_date = datetime.now()
            elif start_date and not end_date:
                is_current = True
                end_date = datetime.now()

            if raw_dates and not start_date:
                logger.warning(
                    f"[EXPERIENCE_DATE_PARSE_UNSUPPORTED] Candidate '{candidate_id or 'unknown'}', Role #{idx} ('{job_title or company or 'Role'}'): Unable to parse raw date string '{raw_dates}'"
                )
                unparsed_dates.append({"role_index": idx, "raw_dates": raw_dates, "job_title": job_title})

            duration_months = None
            if start_date and end_date:
                end_date = max(end_date, start_date)
                end_date = min(end_date, datetime.now())
                valid_intervals.append((start_date, end_date))
                duration_months = cls.interval_duration_months(start_date, end_date)

            normalized_employment.append(
                {
                    "job_title": job_title or "Position",
                    "company": company or "Organization",
                    "dates": raw_dates or "N/A",
                    "start_date": start_date.date().isoformat() if start_date else None,
                    "end_date": end_date.date().isoformat() if end_date and not is_current else None,
                    "is_current": is_current,
                    "duration_months": duration_months,
                }
            )

        merged_intervals = cls._merge_intervals(valid_intervals)
        total_days = sum((end - start).days for start, end in merged_intervals)
        deterministic_years = round(total_days / 365.25, 1) if merged_intervals else None

        stated_years = cls._extract_explicit_experience(cv_text)

        # Resolution hierarchy:
        if deterministic_years is not None and deterministic_years > 0:
            authoritative_years = deterministic_years
            status = "corroborated" if stated_years and abs(deterministic_years - stated_years) <= 1.5 else "date_only"
        elif stated_years is not None and stated_years > 0:
            authoritative_years = stated_years
            status = "stated_fallback"
        elif work_exp:
            authoritative_years = round(max(1.0, float(len(work_exp))), 1)
            status = "role_heuristic"
        else:
            authoritative_years = 0.0
            status = "no_history"

        # Seniority calculation
        if authoritative_years >= 12.0:
            seniority = "Executive / Director"
        elif authoritative_years >= 8.0:
            seniority = "Lead / Principal"
        elif authoritative_years >= 5.0:
            seniority = "Senior"
        elif authoritative_years >= 2.0:
            seniority = "Mid-Level"
        elif authoritative_years >= 0.5 or work_exp:
            seniority = "Junior / Associate"
        else:
            seniority = "Entry Level"

        if authoritative_years > 0:
            experience_assessment = f"Assessed as {seniority} level with {authoritative_years:.1f} years of verified experience."
        elif work_exp:
            experience_assessment = f"Assessed as {seniority} level based on {len(work_exp)} documented employment role(s)."
        else:
            experience_assessment = "Assessed as Entry Level (No employment history documented)."

        return {
            "experience_years": authoritative_years,
            "deterministic_years": deterministic_years,
            "stated_years": stated_years,
            "authoritative_years": authoritative_years,
            "seniority": seniority,
            "experience_assessment": experience_assessment,
            "validation_status": status,
            "merged_intervals_count": len(merged_intervals),
            "unparsed_dates": unparsed_dates,
            "normalized_employment": normalized_employment,
        }

    @classmethod
    def calculate_total_experience(cls, resume_json: dict[str, Any], cv_text: str = "") -> float:
        """
        Calculates total experience using the canonical calculator.
        """
        summary = cls.calculate_canonical_experience(resume_json, cv_text)
        return float(summary["experience_years"])

    @classmethod
    def extract_intervals(cls, resume_json: dict[str, Any]) -> list[tuple[datetime, datetime]]:
        """Return valid employment intervals without applying stated or LLM experience."""
        intervals: list[tuple[datetime, datetime]] = []
        work_experience = resume_json.get("work_experience") or []
        for job in work_experience:
            dates_str = job.get("dates")

            start_date, end_date = None, None
            if dates_str:
                start_date, end_date = cls._extract_date_range(dates_str)

            # Fallback if dates were miscategorized by the parser
            if not start_date:
                fallback_fields = [
                    job.get("job_title"),
                    job.get("company"),
                    job.get("description"),
                ]
                for field in fallback_fields:
                    if field and isinstance(field, str):
                        # Look for a range pattern like "MM/YYYY - MM/YYYY" or "YYYY to Present"
                        if re.search(
                            r"\b(20\d{2}|19\d{2}|present|current|now)\b",
                            field,
                            re.IGNORECASE,
                        ):
                            s_date, e_date = cls._extract_date_range(field)
                            if s_date:
                                start_date, end_date = s_date, e_date
                                break

            # If missing end date but has start date, assume it's the current job
            if start_date and not end_date:
                end_date = datetime.now()

            # If we couldn't parse start date, we can't use this interval
            if not start_date:
                continue

            # Sanity checks
            end_date = max(end_date, start_date)

            # Cap end_date at current time
            end_date = min(end_date, datetime.now())

            intervals.append((start_date, end_date))

        return intervals

    @staticmethod
    def interval_duration_months(start_date: datetime, end_date: datetime) -> int:
        if end_date < start_date:
            return 0
        months = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month
        return max(1, months)

    @classmethod
    def _merge_intervals(cls, intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
        intervals.sort(key=lambda x: x[0])
        merged_intervals: list[tuple[datetime, datetime]] = []
        for interval in intervals:
            if not merged_intervals:
                merged_intervals.append(interval)
            else:
                last_start, last_end = merged_intervals[-1]
                current_start, current_end = interval

                if current_start <= last_end:
                    # Overlap found, extend the last interval if necessary
                    merged_intervals[-1] = (last_start, max(last_end, current_end))
                else:
                    merged_intervals.append(interval)
        return merged_intervals

    @classmethod
    def _extract_explicit_experience(cls, cv_text: str) -> float | None:
        if not cv_text:
            return None

        search_text = cv_text[:2000].lower()

        # Regex to match: "total experience: 5.5 years", "experience - 4 yrs", "5+ years of experience"
        patterns = [
            r"(?:total\s+)?(?:experience|exp)\s*(?:[:\-\|]|\s)\s*(\d{1,2}(?:\.\d{1,2})?)\+?\s*(?:years?|yrs?)",
            r"(\d{1,2}(?:\.\d{1,2})?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:total\s+)?(?:experience|exp)",
        ]

        for p in patterns:
            match = re.search(p, search_text)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        return None
