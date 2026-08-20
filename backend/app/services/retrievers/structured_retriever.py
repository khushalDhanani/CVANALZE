from __future__ import annotations
from typing import Any

from app.core.rule_config_manager import PolicyRegistry
from app.repositories.result import ResultRepository


class StructuredCandidateRetriever:
    """
    Decoupled Structured Candidate Retriever.
    Executes database-level deterministic filtering based on experience range, location, department, and candidate status.
    Does NOT depend on domain-specific hardcoded keywords or application rules.
    """

    @classmethod
    def retrieve_candidates(
        cls,
        filters: dict[str, Any],
        top_k: int | None = None,
    ) -> dict[str, int]:
        """
        Filter candidate results based on structured filter constraints.
        Returns a dict mapping cv_key (str) to structured rank (1-indexed).
        """
        top_k = top_k or PolicyRegistry.resolve_snapshot().retrieval.vector_candidate_pool
        ranks: dict[str, int] = {}
        if not filters:
            return ranks

        include_inc = bool(filters.get("include_incomplete", False))
        results = ResultRepository.list_all_results(include_incomplete=include_inc)
        if not results:
            return ranks

        min_exp = filters.get("min_experience")
        max_exp = filters.get("max_experience")
        req_dept = (filters.get("department") or "").strip().lower()
        req_loc = (filters.get("location") or "").strip().lower()
        req_status = (filters.get("status") or "").strip().upper()

        matching_keys: list[str] = []

        for r in results:
            if not r or not isinstance(r, dict):
                continue

            cv_key = str(r.get("id") or r.get("filename") or "").removesuffix(".json")
            if not cv_key:
                continue

            # Experience Filter
            cand_exp = r.get("experience_years")
            if cand_exp is None:
                cand_exp = r.get("total_experience_years")
            if cand_exp is None:
                cand_exp = (r.get("experience_summary") or {}).get("experience_years")

            if min_exp is not None and cand_exp is not None and cand_exp < float(min_exp):
                continue
            if max_exp is not None and cand_exp is not None and cand_exp > float(max_exp):
                continue

            # Department Filter
            if req_dept:
                match_analysis = r.get("match_analysis") or {}
                cand_dept = str(match_analysis.get("primary_department") or "").lower()
                if req_dept not in cand_dept and cand_dept not in req_dept:
                    continue

            # Location Filter
            if req_loc:
                contact_info = (r.get("resume_json") or {}).get("contact_info") or {}
                loc_text = str(r.get("location") or contact_info.get("location") or "").lower()
                markdown_text = str(r.get("markdown") or r.get("text") or "").lower()
                if req_loc not in loc_text and req_loc not in markdown_text:
                    continue

            # Status Filter
            if req_status and req_status != "ALL":
                cand_status = str(r.get("status") or "").upper()
                if cand_status != req_status:
                    continue

            matching_keys.append(cv_key)

        for rank_idx, cv_key in enumerate(matching_keys[:top_k], start=1):
            ranks[cv_key] = rank_idx

        return ranks
