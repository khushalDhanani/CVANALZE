import re
from typing import Any

class ResumeFieldExtractorTest:
    JOB_TITLE_KEYWORDS = {"developer", "manager"}
    _DATE_RANGE = re.compile(r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\.\,\-]+\d{2,4}\s*[\-to]+\s*(?:present|current|now|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\.\,\-]+\d{2,4})|(?:\b(?:19|20)\d{2}\s*[\-to]+\s*(?:present|current|now|\b(?:19|20)\d{2})))", re.IGNORECASE)

    @classmethod
    def is_valid_job_title(cls, text: str) -> bool:
        if "developer" in text.lower() or "engineer" in text.lower() or "manager" in text.lower():
            return True
        return False
        
    @classmethod
    def is_valid_company_name(cls, text: str) -> bool:
        if "llc" in text.lower() or "inc" in text.lower() or "tech" in text.lower() or "solutions" in text.lower():
            return True
        return False
        
    @classmethod
    def _looks_like_company(cls, text: str) -> bool:
        return cls.is_valid_company_name(text)
        
    @classmethod
    def _looks_like_title(cls, text: str) -> bool:
        return cls.is_valid_job_title(text)

    @classmethod
    def _fix_company_title_swap(cls, current: dict[str, Any]) -> None:
        company = current.get("company") or ""
        title = current.get("job_title") or ""
        if company and title and cls._looks_like_title(company) and cls._looks_like_company(title):
            current["company"], current["job_title"] = title, company
        elif company and not title and cls._looks_like_title(company) and not cls._looks_like_company(company):
            current["job_title"] = company
            current["company"] = ""
        elif title and not company and cls._looks_like_company(title) and not cls._looks_like_title(title):
            current["company"] = title
            current["job_title"] = ""

    @classmethod
    def _extract_employment(cls, lines: list[str]) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        current: dict[str, Any] = {}

        def commit() -> None:
            nonlocal current
            has_dates = bool(current.get("dates"))
            has_title = bool(current.get("job_title"))
            has_company = bool(current.get("company"))
            has_resp = bool(current.get("responsibilities"))
            
            if has_dates or (has_title and has_company) or (has_title and has_resp):
                cls._fix_company_title_swap(current)
                jobs.append(current)
            current = {}

        def resolve_unresolved() -> None:
            if not current.get("unresolved_header"):
                return
            for line in current["unresolved_header"]:
                if not current.get("company") and cls._looks_like_company(line):
                    current["company"] = line
                elif not current.get("job_title") and cls.is_valid_job_title(line):
                    current["job_title"] = line
                else:
                    current.setdefault("responsibilities", []).append(line)
            current.pop("unresolved_header", None)

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            date_match = cls._DATE_RANGE.search(line)
            clean_line = line.lstrip("-• \uf0b7").strip()
            
            has_date_match = bool(date_match)
            _desig_prefix_re = re.compile(r"^(?:designation|job\s+title|role|position)\s*[:\-]+\s*", re.IGNORECASE)
            is_explicit_title = bool(_desig_prefix_re.match(clean_line))
            clean_val = _desig_prefix_re.sub("", clean_line).strip() if is_explicit_title else clean_line
            
            is_title = is_explicit_title or cls.is_valid_job_title(clean_val)
            is_strict_company = cls._looks_like_company(clean_val)
            is_greedy_company = is_strict_company or cls.is_valid_company_name(clean_val)
            is_bullet = line.startswith(("-", "•"))

            state_has_title = bool(current.get("job_title"))
            state_has_company = bool(current.get("company"))
            state_has_date = bool(current.get("dates"))
            state_has_resp = bool(current.get("responsibilities"))

            incoming_is_strong_boundary = False
            if not is_bullet:
                if has_date_match and state_has_date:
                    incoming_is_strong_boundary = True
                elif is_explicit_title and state_has_title:
                    incoming_is_strong_boundary = True
                elif is_strict_company and state_has_company and (state_has_resp or state_has_date):
                    incoming_is_strong_boundary = True
                elif is_title and state_has_title and (state_has_date or state_has_resp):
                    incoming_is_strong_boundary = True

            if incoming_is_strong_boundary:
                resolve_unresolved()
                commit()

            if is_bullet:
                current.setdefault("responsibilities", []).append(clean_line)
            else:
                if has_date_match:
                    if not current.get("dates"):
                        current["dates"] = date_match.group(0).strip(" ()")
                else:
                    if is_explicit_title:
                        if not current.get("job_title"):
                            current["job_title"] = clean_val
                        else:
                            current.setdefault("responsibilities", []).append(clean_val)
                    elif is_title and not current.get("job_title"):
                        if is_strict_company and not current.get("company") and not cls._looks_like_title(clean_val):
                            current["company"] = clean_val
                        else:
                            current["job_title"] = clean_val
                    elif is_greedy_company and not current.get("company"):
                        current["company"] = clean_val
                    elif not current.get("company") and not current.get("job_title") and len(clean_line) < 70 and not current.get("dates"):
                        current.setdefault("unresolved_header", []).append(clean_line)
                    else:
                        current.setdefault("responsibilities", []).append(clean_line)

        resolve_unresolved()
        commit()
        return jobs

import pprint
res = ResumeFieldExtractorTest._extract_employment([
    "ASP .NET Developer",
    "Pulse Software Solutions LLC",
    "07/2021 - Present",
    "Surat, India",
    "- Developed admin panels using ASP.NET Core",
    "- Managed SQL Server databases",
    "Software Engineer",
    "Some Tech Inc",
    "2018 - 2021",
    "- Did something else"
])
pprint.pprint(res)
