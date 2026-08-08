from __future__ import annotations
import calendar
import logging
import re
from datetime import datetime

from dateutil import parser as dateutil_parser

from app.schemas.normalized_resume import NormalizedDateInterval

logger = logging.getLogger("cv_analyzer")


class DateIntervalParser:
    """
    Configurable, locale-aware, cross-platform date interval parser.
    Handles diverse date formats, separators, present/current synonyms,
    partial dates, seasons, 2-digit years, and fuzzy date strings.
    """

    PRESENT_KEYWORDS = {
        "present", "current", "now", "till date", "to date", "onwards",
        "till now", "currently", "presently", "actual", "heute", "aujourd'hui",
        "date", "ongoing", "continue", "continuing", "in progress", "active",
        "till present", "to present", "till current",
    }

    MONTH_MAP = {
        # English
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
        "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
        # Spanish / French / German
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
        "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
        "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
        "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10,
        "novembre": 11, "décembre": 12, "decembre": 12,
        "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "juni": 6, "juli": 7,
        "oktober": 10, "dezember": 12,
    }

    RANGE_SPLIT_REGEX = re.compile(
        r"(?:\s*(?:[–—~]|->|\bto\b|\btill\b|\buntil\b|\bthrough\b|\bbis\b|\ba\b)\s*|\s*[-–—]\s*|(?<=\d{4})-(?=\d{2,4})|(?<=\d{2}/\d{4})-(?=\d{2}/\d{4}))",
        re.IGNORECASE,
    )

    @classmethod
    def is_present(cls, text: str) -> bool:
        if not text:
            return False
        cleaned = text.strip().lower()
        return any(re.search(rf"\b{re.escape(kw)}\b", cleaned) for kw in cls.PRESENT_KEYWORDS)

    @classmethod
    def parse_date_point(cls, date_str: str, is_end_date: bool = False, ref_date: datetime | None = None) -> tuple[datetime | None, float]:
        """
        Parse a single date point string (start or end date).
        Returns (datetime, confidence).
        """
        if not date_str:
            return None, 0.0

        target_ref = ref_date or datetime.now()
        cleaned = date_str.strip().lower()
        cleaned = re.sub(r"^(?:from|since|starting|as of)\s+", "", cleaned).strip(" ()[],'\"")

        if cls.is_present(cleaned):
            return target_ref, 1.0

        # 1. Full ISO date YYYY-MM-DD or DD/MM/YYYY
        m = re.search(r"\b(19\d{2}|20\d{2})[/\.\-](0?[1-9]|1[0-2])[/\.\-](0?[1-9]|[12]\d|3[01])\b", cleaned)
        if m:
            try:
                dt = datetime(year=int(m.group(1)), month=int(m.group(2)), day=int(m.group(3)))
                return dt, 1.0
            except ValueError:
                pass

        m = re.search(r"\b(0?[1-9]|[12]\d|3[01])[/\.\-](0?[1-9]|1[0-2])[/\.\-](19\d{2}|20\d{2})\b", cleaned)
        if m:
            try:
                dt = datetime(year=int(m.group(3)), month=int(m.group(2)), day=int(m.group(1)))
                return dt, 1.0
            except ValueError:
                pass

        # 2. MM/YYYY or MM-YYYY
        m = re.search(r"\b(0?[1-9]|1[0-2])[/\.\-](19\d{2}|20\d{2})\b", cleaned)
        if m:
            year, month = int(m.group(2)), int(m.group(1))
            day = calendar.monthrange(year, month)[1] if is_end_date else 1
            return datetime(year=year, month=month, day=day), 0.95

        # 3. YYYY-MM or YYYY/MM
        m = re.search(r"\b(19\d{2}|20\d{2})[/\.\-](0?[1-9]|1[0-2])\b", cleaned)
        if m:
            year, month = int(m.group(1)), int(m.group(2))
            day = calendar.monthrange(year, month)[1] if is_end_date else 1
            return datetime(year=year, month=month, day=day), 0.95

        # 4. Month Name + YYYY (e.g. "Jan 2020", "January 2020", "Jan. 2020", "Enero 2020")
        m = re.search(r"\b([a-zà-ÿ]{3,10})\.?\s*,?\s*(19\d{2}|20\d{2})\b", cleaned)
        if m:
            month_str = m.group(1).rstrip(".")
            year = int(m.group(2))
            if month_str in cls.MONTH_MAP:
                month = cls.MONTH_MAP[month_str]
                day = calendar.monthrange(year, month)[1] if is_end_date else 1
                return datetime(year=year, month=month, day=day), 0.95

        # 5. Seasons / Quarters (e.g. Q1 2020, Summer 2021)
        m = re.search(r"\b(q[1-4]|summer|winter|spring|fall|verano|invierno|primavera|otoño)\s+(19\d{2}|20\d{2})\b", cleaned)
        if m:
            term = m.group(1)
            year = int(m.group(2))
            q_map = {
                "q1": (1, 3), "spring": (3, 5), "primavera": (3, 5),
                "q2": (4, 6), "summer": (6, 8), "verano": (6, 8),
                "q3": (7, 9), "fall": (9, 11), "otoño": (9, 11),
                "q4": (10, 12), "winter": (12, 2), "invierno": (12, 2),
            }
            start_m, end_m = q_map.get(term, (1, 12))
            month = end_m if is_end_date else start_m
            day = calendar.monthrange(year, month)[1] if is_end_date else 1
            return datetime(year=year, month=month, day=day), 0.85

        # 6. YYYY (4-digit year)
        m = re.search(r"\b(19\d{2}|20\d{2})\b", cleaned)
        if m:
            year = int(m.group(1))
            month = 12 if is_end_date else 1
            day = 31 if is_end_date else 1
            return datetime(year=year, month=month, day=day), 0.80

        # 7. 2-digit year (for end dates like "21" in "2018 - 21" or "04/20")
        m_2d_month = re.search(r"\b(0?[1-9]|1[0-2])[/\.\-](\d{2})\b", cleaned)
        if m_2d_month:
            yr_2digit = int(m_2d_month.group(2))
            year = (2000 + yr_2digit) if yr_2digit <= 35 else (1900 + yr_2digit)
            month = int(m_2d_month.group(1))
            day = calendar.monthrange(year, month)[1] if is_end_date else 1
            return datetime(year=year, month=month, day=day), 0.85

        m = re.search(r"\b(\d{2})\b", cleaned)
        if m and is_end_date:
            yr_2digit = int(m.group(1))
            year = (2000 + yr_2digit) if yr_2digit <= 35 else (1900 + yr_2digit)
            return datetime(year=year, month=12, day=31), 0.70

        # 8. Dateutil fuzzy fallback — only when the text contains an explicit
        #    date anchor (month name or 2/4-digit year token).
        try:
            anchor = re.search(
                r"\b(?:19\d{2}|20\d{2}|\d{2})\b|\b[a-zà-ÿ]{3,10}\b", cleaned
            )
            if not anchor:
                return None, 0.0
            parsed = dateutil_parser.parse(cleaned, fuzzy=True, default=datetime(2000, 1, 1))
            # Reject when the year came from the 2000 sentinel default (no explicit year).
            if parsed.year == 2000 and not re.search(r"\b(?:19\d{2}|20\d{2})\b", cleaned):
                return None, 0.0
            if 1970 <= parsed.year <= (ref_date or datetime.now()).year + 1:
                day = calendar.monthrange(parsed.year, parsed.month)[1] if is_end_date else parsed.day
                return datetime(year=parsed.year, month=parsed.month, day=day), 0.60
        except (ValueError, OverflowError):
            pass

        return None, 0.0

    @classmethod
    def parse_interval(cls, raw_value: str | None, ref_date: datetime | None = None) -> NormalizedDateInterval:
        """
        Parse raw date string into typed NormalizedDateInterval with confidence and evidence.
        """
        if not raw_value or not raw_value.strip():
            return NormalizedDateInterval(confidence=0.0)

        target_ref = ref_date or datetime.now()
        cleaned = raw_value.strip().strip("()[]")
        parts = cls.RANGE_SPLIT_REGEX.split(cleaned.lower(), maxsplit=1)

        start_date, start_conf = None, 0.0
        end_date, end_conf = None, 0.0
        is_current = cls.is_present(cleaned)

        if len(parts) >= 2 and parts[0].strip() != parts[1].strip():
            start_date, start_conf = cls.parse_date_point(parts[0], is_end_date=False, ref_date=target_ref)
            end_date, end_conf = cls.parse_date_point(parts[1], is_end_date=True, ref_date=target_ref)
            if not is_current:
                is_current = cls.is_present(parts[1])

        if not start_date:
            start_date, start_conf = cls.parse_date_point(cleaned, is_end_date=False, ref_date=target_ref)
            if not is_current:
                end_date, end_conf = cls.parse_date_point(cleaned, is_end_date=True, ref_date=target_ref)

        # Handle "Since May 2020" or "From 2019" without explicit end date
        if start_date and not end_date:
            if is_current or re.search(r"\b(?:since|from|starting|as of)\b", cleaned.lower()):
                is_current = True
                end_date = target_ref
                end_conf = 1.0

        if start_date and is_current and not end_date:
            end_date = target_ref
            end_conf = 1.0

        if start_date and end_date:
            if end_date < start_date:
                end_date = start_date
            end_date = min(end_date, target_ref)

        duration_months = None
        if start_date and end_date:
            months = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1
            duration_months = max(1, months)

        overall_conf = round((start_conf + end_conf) / 2.0, 2) if (start_date and end_date) else round(start_conf, 2)

        return NormalizedDateInterval(
            raw_value=cleaned,
            start_date=start_date.date().isoformat() if start_date else None,
            end_date=None if is_current else (end_date.date().isoformat() if end_date else None),
            is_current=is_current,
            duration_months=duration_months,
            confidence=overall_conf,
            evidence=[cleaned],
        )
