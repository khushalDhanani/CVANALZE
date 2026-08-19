from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import logger


@dataclass
class QueryContext:
    """
    Encapsulates dynamic query analysis results:
    raw query text, normalized query, extracted phrases, tokens, concepts, structured filters, and semantic search prompt.
    """
    raw_query: str
    normalized_query: str
    phrases: list[str] = field(default_factory=list)
    tokens: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    semantic_text: str = ""


class SearchQueryAnalyzer:
    """
    Dynamic, domain-agnostic search query analysis service.
    Extracts terms, quoted phrases, numerical range filters, and concepts from natural language text or structured vacancy inputs.
    Does NOT use hardcoded keyword lists or application-level special cases.
    """

    _QUOTED_PHRASE_PATTERN = re.compile(r'"([^"]+)"|\'([^\']+)\'')
    _NUMERIC_FILTER_PATTERNS = [
        re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:\+|\s*plus|\s*to\s*(\d+(?:\.\d+)?))\s*(?:years?|yrs?)\b", re.IGNORECASE),
        re.compile(r"\b(?:min|minimum|at\s+least)\s+(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\b", re.IGNORECASE),
        re.compile(r"\b(?:max|maximum|up\s+to)\s+(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\b", re.IGNORECASE),
    ]

    @classmethod
    def analyze_query(
        cls,
        query: str | None = None,
        vacancy_data: dict[str, Any] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> QueryContext:
        """
        Analyze incoming query string or structured vacancy data and build a QueryContext.
        """
        raw_text = (query or "").strip()
        vac_dict = vacancy_data or {}
        explicit_filters = dict(filters or {})

        if not raw_text and vac_dict:
            raw_text = cls._build_text_from_vacancy(vac_dict)

        normalized_text = cls._normalize_text(raw_text)

        phrases = cls._extract_phrases(raw_text)
        tokens = cls._extract_tokens(normalized_text)

        extracted_filters = cls._extract_dynamic_filters(raw_text)
        merged_filters = {**extracted_filters, **explicit_filters}

        concepts = cls._extract_concepts(normalized_text, vac_dict, phrases)

        semantic_parts = []
        if phrases:
            semantic_parts.append(" ".join(phrases))
        if concepts:
            semantic_parts.append(" ".join(concepts))
        if normalized_text:
            semantic_parts.append(normalized_text)

        semantic_text = " ".join(dict.fromkeys(semantic_parts)).strip()

        return QueryContext(
            raw_query=raw_text,
            normalized_query=normalized_text,
            phrases=phrases,
            tokens=tokens,
            concepts=concepts,
            filters=merged_filters,
            semantic_text=semantic_text,
        )

    @classmethod
    def _normalize_text(cls, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip().lower()
        return cleaned

    @classmethod
    def _extract_phrases(cls, text: str) -> list[str]:
        phrases: list[str] = []
        for match in cls._QUOTED_PHRASE_PATTERN.finditer(text):
            phrase = (match.group(1) or match.group(2) or "").strip()
            if phrase:
                phrases.append(phrase)
        return phrases

    @classmethod
    def _extract_tokens(cls, text: str) -> list[str]:
        words = re.findall(r"[\w+#.]+", text)
        stop_words = {"the", "a", "an", "and", "or", "in", "of", "to", "for", "with", "on", "at", "by", "from", "is", "are", "be", "with"}
        tokens = [w for w in words if len(w) >= 2 and w.lower() not in stop_words]
        return tokens

    @classmethod
    def _extract_dynamic_filters(cls, text: str) -> dict[str, Any]:
        filters: dict[str, Any] = {}

        for pattern in cls._NUMERIC_FILTER_PATTERNS:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                if len(groups) >= 2 and groups[1]:
                    filters["min_experience"] = float(groups[0])
                    filters["max_experience"] = float(groups[1])
                elif groups[0]:
                    val = float(groups[0])
                    if "up to" in text.lower() or "max" in text.lower():
                        filters["max_experience"] = val
                    else:
                        filters["min_experience"] = val
                break

        return filters

    @classmethod
    def _extract_concepts(
        cls,
        normalized_text: str,
        vacancy_data: dict[str, Any],
        phrases: list[str],
    ) -> list[str]:
        concepts: set[str] = set()

        for p in phrases:
            concepts.add(p.lower())

        if vacancy_data:
            title = vacancy_data.get("title") or vacancy_data.get("job_title")
            if title:
                concepts.add(str(title).lower())
            req_skills = vacancy_data.get("required_skills") or vacancy_data.get("skills") or []
            if isinstance(req_skills, list):
                for s in req_skills:
                    if isinstance(s, str) and s.strip():
                        concepts.add(s.strip().lower())
            dept = vacancy_data.get("department_name") or vacancy_data.get("department")
            if dept:
                concepts.add(str(dept).lower())

        try:
            from app.services.dynamic_taxonomy_service import DynamicTaxonomyService

            if normalized_text:
                res = DynamicTaxonomyService.resolve_candidate_role_and_domain(normalized_text)
                if res and res.db_department_name:
                    concepts.add(res.db_department_name.lower())
                if res and res.db_designation_name:
                    concepts.add(res.db_designation_name.lower())
        except Exception as exc:
            logger.debug(f"[QUERY_ANALYZER] Dynamic Taxonomy lookup bypassed: {exc}")

        return [c for c in concepts if c]

    @classmethod
    def _build_text_from_vacancy(cls, vac_dict: dict[str, Any]) -> str:
        parts = []
        if vac_dict.get("title"):
            parts.append(str(vac_dict["title"]))
        if vac_dict.get("department_name") or vac_dict.get("department"):
            parts.append(str(vac_dict.get("department_name") or vac_dict.get("department")))
        if vac_dict.get("required_skills"):
            skills = vac_dict["required_skills"]
            skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)
            parts.append(f"Skills: {skills_str}")
        if vac_dict.get("job_description"):
            parts.append(str(vac_dict["job_description"]))
        return "\n".join(parts).strip()
