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
        if not date_str:
            return None

        date_str = date_str.strip().lower()

        # Check for Present/Current
        if re.search(r"\b(present|current|now|till date|to date|onwards|till now|currently|presently)\b", date_str):
            return datetime.now()

        # 1. Full dates: YYYY-MM-DD or DD/MM/YYYY or Mon DD, YYYY
        m = re.search(r"\b(19\d{2}|20\d{2})[/\.\-](0?[1-9]|1[0-2])[/\.\-](0?[1-9]|[12]\d|3[01])\b", date_str)
        if m:
            return datetime(year=int(m.group(1)), month=int(m.group(2)), day=int(m.group(3)))

        m = re.search(r"\b(0?[1-9]|[12]\d|3[01])[/\.\-](0?[1-9]|1[0-2])[/\.\-](19\d{2}|20\d{2})\b", date_str)
        if m:
            return datetime(year=int(m.group(3)), month=int(m.group(2)), day=1)

        # 2. MM/YYYY, MM-YYYY, MM.YYYY
        m = re.search(r"\b(0?[1-9]|1[0-2])[/\.\-](19\d{2}|20\d{2})\b", date_str)
        if m:
            return datetime(year=int(m.group(2)), month=int(m.group(1)), day=1)

        # 3. YYYY-MM, YYYY/MM, YYYY.MM
        m = re.search(r"\b(19\d{2}|20\d{2})[/\.\-](0?[1-9]|1[0-2])\b", date_str)
        if m:
            return datetime(year=int(m.group(1)), month=int(m.group(2)), day=1)

        # 4. Mon YYYY or Month YYYY
        m = re.search(r"\b([a-z]{3,9})\.?\s+(19\d{2}|20\d{2})\b", date_str)
        if m:
            month_str = m.group(1).rstrip(".")
            year = int(m.group(2))
            if month_str in cls.MONTH_MAP:
                return datetime(year=year, month=cls.MONTH_MAP[month_str], day=1)

        # 5. Q1-Q4 YYYY or Seasons
        m = re.search(r"\b(q[1-4]|summer|winter|spring|fall)\s+(19\d{2}|20\d{2})\b", date_str)
        if m:
            q_or_season = m.group(1)
            year = int(m.group(2))
            month_mapping = {
                "q1": 1, "spring": 3,
                "q2": 4, "summer": 6,
                "q3": 7, "fall": 9,
                "q4": 10, "winter": 12,
            }
            month = month_mapping.get(q_or_season, 1)
            return datetime(year=year, month=month, day=1)

        # 6. YYYY (4-digit year)
        m = re.search(r"\b(19\d{2}|20\d{2})\b", date_str)
        if m:
            year = int(m.group(1))
            month = 12 if is_end_date else 1
            return datetime(year=year, month=month, day=1)

        # 7. 2-digit short year for end date (e.g. "21" in "2018 - 21")
        m = re.search(r"\b(\d{2})\b", date_str)
        if m and is_end_date:
            yr_2digit = int(m.group(1))
            if 0 <= yr_2digit <= 35:
                year = 2000 + yr_2digit
            else:
                year = 1900 + yr_2digit
            return datetime(year=year, month=12, day=1)

        return None

    @classmethod
    def _extract_date_range(cls, dates_str: str) -> tuple[datetime | None, datetime | None]:
        if not dates_str:
            return None, None

        cleaned = dates_str.lower().strip()

        # Check for range separators: - , – , — , ~ , -> , to , till , until
        # Don't split ISO dates (YYYY-MM or MM/YYYY) unless separator is clearly a range divider.
        # Match range pattern: <part1> <separator> <part2>
        sep_pattern = r"(?:\s*(?:[–—~]|->|\bto\b|\btill\b|\buntil\b)\s*|\s+-\s+|\s*/\s*|(?<=\d{4})-(?=\d{2,4}))"
        parts = re.split(sep_pattern, cleaned, maxsplit=1)

        if len(parts) >= 2 and parts[0] != parts[1]:
            start_date = cls._parse_date(parts[0], is_end_date=False)
            end_date = cls._parse_date(parts[1], is_end_date=True)
            if start_date or end_date:
                return start_date, end_date

        start_date = cls._parse_date(cleaned, is_end_date=False)
        end_date = cls._parse_date(cleaned, is_end_date=True)
        return start_date, end_date

    @classmethod
    def calculate_total_experience(cls, resume_json: dict[str, Any], cv_text: str = "") -> float:
        """
        Calculates total experience by extracting dates, merging overlapping periods,
        and validating against any explicitly stated experience.
        """
        intervals = cls.extract_intervals(resume_json)
        merged_intervals = cls._merge_intervals(intervals)
        calculated_years = round(sum((end - start).days for start, end in merged_intervals) / 365.25, 1)
        explicit_years = cls._extract_explicit_experience(cv_text)

        if explicit_years is not None:
            diff = abs(calculated_years - explicit_years)
            level = "Significant mismatch" if diff > 1.5 else "Validation match"
            logger.info(f"[EXPERIENCE] {level}: calculated={calculated_years} years, stated={explicit_years} years. Keeping date-derived value authoritative.")

        return calculated_years

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
