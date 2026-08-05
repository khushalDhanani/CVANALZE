import json
import logging
from typing import List, Optional

from app.core.database import SessionLocal
from app.core.rule_config_manager import RuleConfigManager
from app.models.domain import DepartmentDomainMaster

from app.schemas.classification_types import NormalizedClassification

logger = logging.getLogger("cv_analyzer")

class DepartmentNormalizer:
    """Service that normalizes internal department/designation names to industry-standard labels.

    It first attempts to load explicit alias mappings from the `DepartmentDomainMaster` table, which contains
    a `Keywords` column with comma‑separated internal names and a `DomainName` column with the industry label.
    If a mapping is not found, it falls back to fuzzy matching against the canonical department list
    provided by the taxonomy rules, with optional heuristics.
    The results are cached in‑memory and refreshed on a configurable interval.
    """

    _cache: dict[str, dict] = {}
    _last_refresh: float = 0.0
    _refresh_interval_seconds: int = 300  # 5 minutes

    @classmethod
    def _load_mappings(cls) -> None:
        """Load alias mappings from the database into the in‑memory cache.

        The cache structure is:
            {
                "internal_name_lower": {
                    "industry_label": str,
                    "department_id": Optional[int],
                },
                ...
            }
        """
        if SessionLocal is None:
            logger.warning("[DepartmentNormalizer] No DB session available; cannot load mappings.")
            return
        try:
            with SessionLocal() as session:
                rows = session.query(DepartmentDomainMaster).all()
                for row in rows:
                    # Use the Keywords column (comma‑separated) to map possible internal names to the domain label
                    keywords = []
                    if row.Keywords:
                        keywords = [kw.strip().lower() for kw in row.Keywords.split(',') if kw.strip()]
                    # If no keywords, fall back to using the DomainName itself as a possible key
                    if not keywords:
                        keywords = [row.DomainName.strip().lower()]
                    for key in keywords:
                        cls._cache[key] = {
                            "industry_label": row.DomainName,
                            "department_id": getattr(row, "DepartmentId", None),
                        }
            logger.info(f"[DepartmentNormalizer] Loaded {len(cls._cache)} alias mappings.")
        except Exception as exc:
            logger.error(f"[DepartmentNormalizer] Failed to load alias mappings: {exc}")

    @classmethod
    def _ensure_cache(cls) -> None:
        import time
        now = time.time()
        if now - cls._last_refresh > cls._refresh_interval_seconds:
            cls._load_mappings()
            cls._last_refresh = now

    @classmethod
    def normalize_department(cls, internal_name: Optional[str]) -> dict:
        """Return a dict with ``industry_department`` and optional ``db_department_id``.

        If ``internal_name`` is ``None`` or empty, returns empty values.
        """
        if not internal_name:
            return {"industry_department": None, "db_department_id": None}
        cls._ensure_cache()
        key = internal_name.strip().lower()
        if key in cls._cache:
            mapping = cls._cache[key]
            return {"industry_department": mapping["industry_label"], "db_department_id": mapping.get("department_id")}
        # Fallback: heuristic fuzzy match against canonical list from RuleConfigManager
        canonical = RuleConfigManager.get_taxonomy_rules().canonical_domains
        # Simple heuristic: case‑insensitive containment
        for domain in canonical:
            if domain.lower() in key:
                return {"industry_department": domain, "db_department_id": None}
        # No match found
        return {"industry_department": None, "db_department_id": None}

    @classmethod
    def normalize_designation(cls, internal_name: Optional[str]) -> dict:
        """Return a dict with ``industry_designation``.

        Looks up explicit designation alias mappings first, then falls back
        to heuristic title-casing of the internal name after stripping
        bracketed suffixes (e.g. ``"Sr. Developer (.NET)"`` → ``"Senior Developer .NET"``).
        """
        if not internal_name:
            return {"industry_designation": None}
        cls._ensure_cache()
        key = internal_name.strip().lower()
        # Check the shared alias cache — DomainName doubles as industry designation label if mapped
        if key in cls._cache:
            return {"industry_designation": cls._cache[key]["industry_label"]}
        # Heuristic: strip parenthetical suffixes, normalise abbreviations, title-case
        import re as _re
        clean = _re.sub(r"\s*\(.*?\)", "", internal_name).strip()
        
        # Expand common abbreviations from DB
        from app.services.taxonomy_service import TaxonomyService
        abbr_map = TaxonomyService.get_abbreviations()
        
        # We need to replace whole words case-insensitively
        # We can split the text and replace
        parts = clean.split()
        for i, part in enumerate(parts):
            lower_part = part.lower()
            if lower_part in abbr_map:
                parts[i] = abbr_map[lower_part]
                
        clean = " ".join(parts).strip().title()
        return {"industry_designation": clean if clean else None}
