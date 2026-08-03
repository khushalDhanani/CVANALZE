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
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12
    }

    @classmethod
    def _parse_date(cls, date_str: str, is_end_date: bool = False) -> datetime | None:
        if not date_str:
            return None
        
        date_str = date_str.strip().lower()
        
        # Check for Present/Current
        if re.search(r"\b(present|current|now|till date|to date)\b", date_str):
            return datetime.now()
            
        # Common formats:
        # 1. MM/YYYY or MM-YYYY
        m = re.search(r"\b(0?[1-9]|1[0-2])[/\-](\d{4})\b", date_str)
        if m:
            return datetime(year=int(m.group(2)), month=int(m.group(1)), day=1)
            
        # 2. YYYY-MM
        m = re.search(r"\b(\d{4})[/\-](0?[1-9]|1[0-2])\b", date_str)
        if m:
            return datetime(year=int(m.group(1)), month=int(m.group(2)), day=1)
            
        # 3. Mon YYYY or Month YYYY
        m = re.search(r"\b([a-z]{3,9})\s+(\d{4})\b", date_str)
        if m:
            month_str = m.group(1)
            year = int(m.group(2))
            if month_str in cls.MONTH_MAP:
                return datetime(year=year, month=cls.MONTH_MAP[month_str], day=1)
                
        # 4. YYYY (Only year provided)
        m = re.search(r"\b(\d{4})\b", date_str)
        if m:
            year = int(m.group(1))
            # If start date, assume Jan 1. If end date, assume Dec 1 to give full year credit.
            month = 12 if is_end_date else 1
            return datetime(year=year, month=month, day=1)
            
        return None

    @classmethod
    def _extract_date_range(cls, dates_str: str) -> tuple[datetime | None, datetime | None]:
        # Split by common separators: " - ", " to ", " – "
        parts = re.split(r"\s*(?:-|to|–|—)\s*", dates_str.lower())
        
        if len(parts) >= 2:
            start_date = cls._parse_date(parts[0], is_end_date=False)
            end_date = cls._parse_date(parts[-1], is_end_date=True)
            return start_date, end_date
        
        # If no separator found, it might just be a single date (e.g. year)
        start_date = cls._parse_date(dates_str, is_end_date=False)
        end_date = cls._parse_date(dates_str, is_end_date=True)
        return start_date, end_date

    @classmethod
    def calculate_total_experience(cls, resume_json: dict[str, Any], cv_text: str = "") -> float:
        """
        Calculates total experience by extracting dates, merging overlapping periods,
        and validating against any explicitly stated experience.
        """
        intervals: list[tuple[datetime, datetime]] = []
        
        work_experience = resume_json.get("work_experience") or []
        for job in work_experience:
            dates_str = job.get("dates")
            
            start_date, end_date = None, None
            if dates_str:
                start_date, end_date = cls._extract_date_range(dates_str)
                
            # Fallback if dates were miscategorized by the parser
            if not start_date:
                fallback_fields = [job.get("job_title"), job.get("company"), job.get("description")]
                for field in fallback_fields:
                    if field and isinstance(field, str):
                        # Look for a range pattern like "MM/YYYY - MM/YYYY" or "YYYY to Present"
                        if re.search(r"\b(20\d{2}|19\d{2}|present|current|now)\b", field, re.IGNORECASE):
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
            if end_date < start_date:
                end_date = start_date
                
            # Cap end_date at current time
            if end_date > datetime.now():
                end_date = datetime.now()
                
            intervals.append((start_date, end_date))
            
        # Merge overlapping intervals
        intervals.sort(key=lambda x: x[0])
        merged_intervals = []
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
                    
        # Calculate total days
        total_days = 0
        for start, end in merged_intervals:
            delta = end - start
            total_days += delta.days
            
        calculated_years = total_days / 365.25
        calculated_years = round(calculated_years, 1)
        
        # Extract explicit experience from CV text (first 2000 chars)
        explicit_years = cls._extract_explicit_experience(cv_text)
        
        if explicit_years is not None:
            # Validate calculated vs explicit
            diff = abs(calculated_years - explicit_years)
            if diff > 1.5:
                logger.warning(
                    f"[EXPERIENCE] Significant mismatch: Calculated {calculated_years} yrs vs "
                    f"Explicit {explicit_years} yrs. Defaulting to calculated."
                )
                return calculated_years
            else:
                logger.info(
                    f"[EXPERIENCE] Explicit experience matches calculated well "
                    f"({explicit_years} vs {calculated_years}). Using calculated for precision."
                )
                return max(calculated_years, explicit_years)
                
        return calculated_years

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
