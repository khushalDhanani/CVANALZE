from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.core.rule_config_manager import RuleConfigManager
from app.schemas.normalized_resume import (
    NormalizedContact,
    NormalizedDateInterval,
    NormalizedEducation,
    NormalizedEmployment,
    NormalizedExperienceSummary,
    NormalizedResume,
    NormalizedSkill,
    NormalizedStringField,
)
from app.services.experience_calculator import ExperienceCalculator


class ResumeNormalizer:
    _SKILL_CASING = {
        "aws": "AWS",
        "c#": "C#",
        "c++": "C++",
        "css": "CSS",
        "docker": "Docker",
        "fastapi": "FastAPI",
        "git": "Git",
        "html": "HTML",
        "javascript": "JavaScript",
        "node.js": "Node.js",
        "postgresql": "PostgreSQL",
        "python": "Python",
        "react": "React",
        "sql": "SQL",
        "typescript": "TypeScript",
    }
    _SKILL_ALIASES = {
        "js": "JavaScript",
        "nodejs": "Node.js",
        "node js": "Node.js",
        "postgres": "PostgreSQL",
        "py": "Python",
        "reactjs": "React",
        "ts": "TypeScript",
    }

    @classmethod
    def normalize(cls, resume_json: dict[str, Any], cv_text: str = "") -> NormalizedResume:
        contact_info = resume_json.get("contact_info") or {}
        employment = [cls._normalize_employment(item) for item in resume_json.get("work_experience") or []]
        skills_data = resume_json.get("skills") or {}
        raw_skills = skills_data.get("all_skills") or [] if isinstance(skills_data, dict) else skills_data
        
        canonical_exp = ExperienceCalculator.calculate_canonical_experience(resume_json, cv_text)

        return NormalizedResume(
            contact=NormalizedContact(
                email=cls._normalize_email(contact_info.get("email")),
                phone=cls._normalize_phone(contact_info.get("phone")),
            ),
            skills=cls._normalize_skills(raw_skills),
            education=[cls._normalize_education(item) for item in resume_json.get("education") or []],
            employment=employment,
            experience=cls._experience_summary_from_canonical(canonical_exp),
        )

    @staticmethod
    def _normalize_email(raw_value: Any) -> NormalizedStringField:
        raw = str(raw_value) if raw_value is not None else None
        normalized = re.sub(r"\s+", "", raw).lower() if raw else None
        valid = bool(normalized and re.fullmatch(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", normalized))
        return NormalizedStringField(
            raw_value=raw,
            normalized_value=normalized,
            confidence=1.0 if valid else (0.4 if normalized else 0.0),
            evidence=[raw] if raw else [],
        )

    @staticmethod
    def _normalize_phone(raw_value: Any) -> NormalizedStringField:
        raw = str(raw_value) if raw_value is not None else None
        digits = re.sub(r"\D", "", raw or "")
        normalized = f"+{digits}" if raw and raw.strip().startswith("+") and digits else (digits or None)
        confidence = 1.0 if 7 <= len(digits) <= 15 else (0.4 if digits else 0.0)
        return NormalizedStringField(
            raw_value=raw,
            normalized_value=normalized,
            confidence=confidence,
            evidence=[raw] if raw else [],
        )

    @classmethod
    def _normalize_skills(cls, raw_skills: list[Any]) -> list[NormalizedSkill]:
        aliases = RuleConfigManager.get_term_matching_assets().get("aliases", {})
        reverse_aliases: dict[str, str] = {}
        for canonical, alternatives in aliases.items():
            reverse_aliases[str(canonical).strip().lower()] = str(canonical).strip()
            for alternative in alternatives:
                reverse_aliases[str(alternative).strip().lower()] = str(canonical).strip()

        normalized_skills: list[NormalizedSkill] = []
        seen: set[str] = set()
        for value in raw_skills:
            raw = str(value).strip()
            if not raw:
                continue
            lookup = re.sub(r"\s+", " ", raw).lower()
            canonical = cls._SKILL_ALIASES.get(lookup, reverse_aliases.get(lookup, lookup))
            canonical = cls._SKILL_CASING.get(canonical.lower(), cls._display_name(canonical))
            dedup_key = canonical.lower()
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            normalized_skills.append(
                NormalizedSkill(
                    raw_value=raw,
                    normalized_value=canonical,
                    confidence=0.95 if lookup == canonical.lower() else 0.85,
                    evidence=[raw],
                    aliases=[raw] if raw.lower() != canonical.lower() else [],
                )
            )
        return normalized_skills

    @staticmethod
    def _display_name(value: str) -> str:
        if not value:
            return value
        if value.isupper() or any(char in value for char in "+#."):
            return value
        return " ".join(word.capitalize() for word in value.split())

    @classmethod
    def _normalize_education(cls, item: Any) -> NormalizedEducation:
        if not isinstance(item, dict):
            raw_value = cls._as_string(item)
            return NormalizedEducation(
                degree=cls._string_field(
                    raw_value,
                    cls._canonical_degree(raw_value),
                    0.5 if raw_value else 0.0,
                ),
                domain=cls._string_field(
                    raw_value,
                    cls._education_domain(raw_value),
                    0.5 if raw_value else 0.0,
                ),
                evidence=[raw_value] if raw_value else [],
            )
        degree_raw = cls._as_string(item.get("degree"))
        institution_raw = cls._as_string(item.get("institution"))
        dates_raw = cls._as_string(item.get("dates"))
        grade_raw = cls._as_string(item.get("grade"))
        degree = cls._canonical_degree(degree_raw)
        domain = cls._education_domain(degree_raw)
        evidence = [value for value in (degree_raw, institution_raw, dates_raw, grade_raw) if value]

        return NormalizedEducation(
            degree=cls._string_field(degree_raw, degree, 0.9 if degree_raw else 0.0),
            domain=cls._string_field(degree_raw, domain, 0.8 if domain else 0.0),
            institution=cls._string_field(
                institution_raw,
                cls._clean_whitespace(institution_raw),
                0.9 if institution_raw else 0.0,
            ),
            interval=cls._normalize_interval(dates_raw) if dates_raw else None,
            grade=cls._string_field(grade_raw, cls._clean_whitespace(grade_raw), 0.9) if grade_raw else None,
            evidence=evidence,
        )

    @classmethod
    def _normalize_employment(cls, item: Any) -> NormalizedEmployment:
        if not isinstance(item, dict):
            raw_value = cls._as_string(item)
            return NormalizedEmployment(evidence=[raw_value] if raw_value else [])
        title_raw = cls._as_string(item.get("job_title"))
        company_raw = cls._as_string(item.get("company"))
        if company_raw and (re.search(r"^\+?\d[\d\s\.\-\(\)]+$", company_raw.strip()) or "@" in company_raw):
            company_raw = ""
        dates_raw = cls._as_string(item.get("dates"))
        raw_resps = [str(value).strip() for value in item.get("responsibilities") or [] if str(value).strip()]
        responsibilities = [
            resp for resp in raw_resps
            if not (re.search(r"^\+?\d[\d\s\.\-\(\)]+$", resp) or "@" in resp or resp.lower() in {"india", "usa", "uk"})
        ]
        description = cls._as_string(item.get("description"))
        evidence = [value for value in (title_raw, company_raw, dates_raw, description) if value] + responsibilities
        return NormalizedEmployment(
            job_title=cls._string_field(title_raw, cls._clean_whitespace(title_raw), 0.9 if title_raw else 0.0),
            company=cls._string_field(
                company_raw,
                cls._clean_whitespace(company_raw),
                0.9 if company_raw else 0.0,
            ),
            interval=cls._normalize_interval(dates_raw),
            responsibilities=responsibilities,
            evidence=evidence,
        )

    @classmethod
    def _normalize_interval(cls, raw_value: str | None) -> NormalizedDateInterval:
        from app.services.date_interval_parser import DateIntervalParser
        return DateIntervalParser.parse_interval(raw_value)

    @staticmethod
    def _experience_summary_from_canonical(canonical_exp: dict[str, Any]) -> NormalizedExperienceSummary:
        state = canonical_exp.get("experience_state") or "UNKNOWN"
        det_years = canonical_exp.get("deterministic_years")
        stated_years = canonical_exp.get("stated_years")
        auth_years = canonical_exp.get("authoritative_years")
        gross_display = canonical_exp.get("gross_display") or ""
        total_m = canonical_exp.get("total_experience_months")
        
        evidence = []
        if det_years is not None:
            evidence.append(f"{canonical_exp.get('merged_intervals_count', 1)} dated interval(s) ({det_years:.1f} yrs)")
        if stated_years is not None:
            evidence.append(f"CV states {stated_years} years")

        return NormalizedExperienceSummary(
            experience_state=state,
            gross_display=gross_display,
            deterministic_years=det_years,
            stated_years=stated_years,
            authoritative_years=auth_years,
            total_experience_months=total_m,
            authoritative_source="canonical_calculator",
            validation_status=state,
            evidence=evidence,
        )

    @classmethod
    def _canonical_degree(cls, value: str | None) -> str | None:
        if not value:
            return None
        checks = (
            (r"\b(b\.?\s*tech|bachelor of technology)\b", "B.Tech"),
            (r"\b(b\.?\s*e\.?|bachelor of engineering)\b", "B.E."),
            (r"\b(b\.?\s*sc\.?|bachelor of science)\b", "B.Sc."),
            (r"\b(bca|bachelor of computer applications?)\b", "BCA"),
            (r"\b(bba|bachelor of business administration)\b", "BBA"),
            (r"\b(b\.?\s*com\.?|bcom|bachelor of commerce)\b", "B.Com"),
            (r"\b(b\.?\s*a\.?|bachelor of arts)\b", "B.A."),
            (r"\b(b\.?\s*pharm|bachelor of pharmacy)\b", "B.Pharm"),
            (r"\b(b\.?\s*arch|bachelor of architecture)\b", "B.Arch"),
            (r"\b(b\.?\s*des|bachelor of design)\b", "B.Des"),
            (r"\b(b\.?\s*ed|bachelor of education)\b", "B.Ed"),
            (r"\b(l\.?l\.?b|bachelor of laws?)\b", "LLB"),
            (r"\b(m\.?\s*tech|master of technology)\b", "M.Tech"),
            (r"\b(m\.?\s*e\.?|master of engineering)\b", "M.E."),
            (r"\b(m\.?\s*sc\.?|master of science)\b", "M.Sc."),
            (r"\b(mca|master of computer applications?)\b", "MCA"),
            (r"\b(mba|master of business administration)\b", "MBA"),
            (r"\b(m\.?\s*com\.?|mcom|master of commerce)\b", "M.Com"),
            (r"\b(m\.?\s*a\.?|master of arts)\b", "M.A."),
            (r"\b(m\.?\s*pharm|master of pharmacy)\b", "M.Pharm"),
            (r"\b(m\.?\s*arch|master of architecture)\b", "M.Arch"),
            (r"\b(m\.?\s*des|master of design)\b", "M.Des"),
            (r"\b(m\.?\s*ed|master of education)\b", "M.Ed"),
            (r"\b(l\.?l\.?m|master of laws?)\b", "LLM"),
            (r"\b(ph\.?\s*d|doctor of philosophy|doctorate)\b", "Ph.D."),
            (r"\b(pgdm|post graduate diploma in management)\b", "PGDM"),
            (r"\b(pgdca|post graduate diploma in computer applications?)\b", "PGDCA"),
            (r"\b(iti|industrial training institute)\b", "ITI"),
            (r"\b(ca|chartered accountant)\b", "CA"),
            (r"\b(cs|company secretary)\b", "CS"),
            (r"\b(icwa|cma|cost and management accountant)\b", "CMA"),
            (r"\bdiploma\b", "Diploma"),
        )
        for pattern, canonical in checks:
            if re.search(pattern, value, re.IGNORECASE):
                return canonical
        return cls._clean_whitespace(value)

    @staticmethod
    def _education_domain(value: str | None) -> str | None:
        if not value:
            return None

        # 1. Check RuleConfigManager domain embedding canonical equivalents for education_domains
        try:
            from app.core.rule_config_manager import RuleConfigManager
            cfg = RuleConfigManager.get_config()
            canonical_map = cfg.scoring.domain_embedding.canonical_equivalents.get("education_domains", {})
            for raw_k, canon_v in canonical_map.items():
                if re.search(r"\b" + re.escape(raw_k) + r"\b", value, re.IGNORECASE):
                    return canon_v
        except Exception:
            pass

        # 2. Comprehensive standard education domains (engineering, sciences, medical, business, law)
        domains = (
            (r"computer science|software|information technology|\bIT\b|informatics|comput", "Computer Science & IT"),
            (r"mechanical|automobile|automotive|mechatronics", "Mechanical Engineering"),
            (r"electrical|electronics|communication|telecom|instrumentation", "Electrical & Electronics Engineering"),
            (r"civil|structural|construction", "Civil Engineering"),
            (r"chemical engineering|petrochemical|polymer|process engineering", "Chemical Engineering"),
            (r"biomedical|biotechnology|bio-tech|biotech|bioinformatics", "Biomedical & Biotechnology"),
            (r"aerospace|aeronautical|aviation|avionics", "Aerospace Engineering"),
            (r"pharmacy|pharmaceutical|pharmacology|pharmaceutics|\bpharm\b", "Pharmacy & Pharmaceutical Sciences"),
            (r"business|management|finance|account|commerce|economics|marketing|human resources|administration|\bmba\b|\bbba\b|\bb\.?com\b|\bm\.?com\b", "Business & Finance"),
            (r"chemistry|chemical sciences?|organic chemistry|analytical chemistry|\bchemical\b", "Chemical Sciences"),
            (r"physics|applied physics", "Physical Sciences"),
            (r"mathematics|statistics|data science", "Mathematics & Data Science"),
            (r"medicine|nursing|healthcare|medical|clinical", "Medicine & Healthcare"),
            (r"law|legal|jurisprudence|\bllb\b|\bllm\b", "Law & Legal Studies"),
            (r"architecture|urban planning|interior design|\bb\.?arch\b", "Architecture & Design"),
        )
        for pattern, domain in domains:
            if re.search(pattern, value, re.IGNORECASE):
                return domain

        # 3. Check live taxonomy / repository domain matchers if available (from 52-entry seeded taxonomy)
        try:
            from app.repositories.department_domain import department_domain_repository
            matchers = department_domain_repository.get_domain_matchers()
            if matchers:
                best_domain = None
                max_matches = 0
                for matcher in matchers:
                    matches = matcher.keyword_match_count(value)
                    if matches > max_matches:
                        max_matches = matches
                        best_domain = matcher.domain.domain_name
                if best_domain and max_matches >= 2:
                    return best_domain
        except Exception:
            pass

        # 4. Fallback: extract trailing qualification clause
        match = re.search(r"\b(?:in|of)\s+(.+?)(?:\s*[-|,]|$)", value, re.IGNORECASE)
        return ResumeNormalizer._clean_whitespace(match.group(1)) if match else None

    @staticmethod
    def _string_field(raw: str | None, normalized: str | None, confidence: float) -> NormalizedStringField:
        return NormalizedStringField(
            raw_value=raw,
            normalized_value=normalized,
            confidence=confidence,
            evidence=[raw] if raw else [],
        )

    @staticmethod
    def _as_string(value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _clean_whitespace(value: str | None) -> str | None:
        return re.sub(r"\s+", " ", value).strip() if value else None

    @staticmethod
    def _date_string(value: datetime | None) -> str | None:
        return value.date().isoformat() if value else None
