from __future__ import annotations
from typing import Any

from app.core.logging import logger
from app.core.rule_config_manager import PolicyRegistry
from app.repositories.result import ResultRepository
from app.services.match_evaluators import VacancyFitEvaluator, VacancyMatchStatus
from app.services.rank_fusion_service import CandidateRankItem


class CandidateSearchReranker:
    """
    Decouples initial candidate retrieval (Vector + Lexical RRF) from qualitative hiring evaluation.
    Reranks Top-N retrieved candidates using deterministic requirement evidence evaluation,
    vacancy fit scoring, and domain mismatch checks.
    """

    @classmethod
    def rerank_retrieved_candidates(
        cls,
        rank_items: list[CandidateRankItem],
        high_threshold: float | None = None,
        potential_threshold: float | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Rerank retrieved CandidateRankItems by merging RRF retrieval scores with qualitative evidence metrics.
        Returns a list of structured candidate result objects ready for API responses.
        """
        snapshot = PolicyRegistry.resolve_snapshot()
        high_threshold = high_threshold if high_threshold is not None else snapshot.scoring.match_high_threshold
        potential_threshold = (
            potential_threshold
            if potential_threshold is not None
            else snapshot.scoring.match_medium_threshold
        )
        limit = limit if limit is not None else snapshot.retrieval.rerank_top_n
        final_results: list[dict[str, Any]] = []

        for item in rank_items:
            cv_key = item.cv_key
            record = ResultRepository.resolve_result(cv_key)

            if not record or not isinstance(record, dict):
                continue

            raw_match = record.get("match_analysis")
            match_analysis = raw_match if isinstance(raw_match, dict) else {}
            best_match = match_analysis.get("best_match") or {}

            evaluated_openings = [
                opening
                for opening in [*(match_analysis.get("suitable_openings") or []), *(match_analysis.get("unsuitable_openings") or [])]
                if isinstance(opening, dict)
            ]

            if not best_match or VacancyFitEvaluator.classify_opening_fit(best_match, high_threshold, potential_threshold) == VacancyMatchStatus.NO_STRONG_MATCH.value:
                best_match = next(
                    (
                        opening
                        for opening in evaluated_openings
                        if VacancyFitEvaluator.classify_opening_fit(opening, high_threshold, potential_threshold) in {VacancyMatchStatus.MATCHED.value, VacancyMatchStatus.POTENTIAL_MATCH.value}
                    ),
                    {},
                )

            best_match_score = VacancyFitEvaluator.resolve_opening_score(best_match) if best_match else None

            # Calculate composite final score (RRF retrieval score + qualitative evidence score)
            qualitative_score = (
                best_match_score / 100.0
                if best_match_score is not None
                else snapshot.retrieval.missing_qualitative_score
            )
            final_composite_score = round(
                snapshot.retrieval.rerank_retrieval_weight * item.rrf_score
                + snapshot.retrieval.rerank_qualitative_weight * qualitative_score,
                4,
            )

            enhanced_record = dict(record)
            enhanced_record["_rrf_score"] = item.rrf_score
            enhanced_record["_retrieval_sources"] = item.retrieval_sources
            enhanced_record["_final_score"] = final_composite_score
            enhanced_record["best_match_score"] = best_match_score
            enhanced_record["best_match"] = best_match

            final_results.append(enhanced_record)

        # Sort by final composite score descending
        final_results.sort(key=lambda x: x.get("_final_score", 0.0), reverse=True)
        return final_results[:limit]
