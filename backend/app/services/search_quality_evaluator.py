from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any

from app.services.embedding_service import EmbeddingService


@dataclass
class SearchEvaluationMetrics:
    """
    Encapsulates quantitative search quality metrics:
    Recall@K, Precision@K, MRR, NDCG@K, and ANN Recall Loss.
    """
    top_k: int
    recall_at_k: float
    precision_at_k: float
    mrr: float
    ndcg_at_k: float
    ann_recall_loss_pct: float = 0.0


class SearchQualityEvaluator:
    """
    Automated Search Quality & Evaluation Service.
    Measures Recall@K, Precision@K, MRR, NDCG@K, and compares ANN (HNSW) retrieval against exact brute-force cosine distance.
    Does NOT depend on hardcoded skill or domain constants in production evaluation logic.
    """

    @classmethod
    def evaluate_retrieval(
        cls,
        retrieved_ids: list[str],
        relevant_ground_truth_ids: list[str],
        top_k: int = 10,
    ) -> SearchEvaluationMetrics:
        """
        Compute Recall@K, Precision@K, MRR, and NDCG@K for a retrieved candidate ID list against ground truth.
        """
        top_retrieved = retrieved_ids[:top_k]
        truth_set = set(relevant_ground_truth_ids)

        if not truth_set or not top_retrieved:
            return SearchEvaluationMetrics(
                top_k=top_k,
                recall_at_k=0.0,
                precision_at_k=0.0,
                mrr=0.0,
                ndcg_at_k=0.0,
            )

        hits = [1 if cid in truth_set else 0 for cid in top_retrieved]
        hit_count = sum(hits)

        recall = round(hit_count / len(truth_set), 4)
        precision = round(hit_count / len(top_retrieved), 4)

        # Calculate MRR (Mean Reciprocal Rank)
        mrr = 0.0
        for rank_idx, hit in enumerate(hits, start=1):
            if hit:
                mrr = round(1.0 / rank_idx, 4)
                break

        # Calculate DCG@K and IDCG@K for NDCG@K
        dcg = sum((2**hit - 1) / math.log2(rank_idx + 1) for rank_idx, hit in enumerate(hits, start=1))
        ideal_hits = [1] * min(len(truth_set), top_k)
        idcg = sum((2**hit - 1) / math.log2(rank_idx + 1) for rank_idx, hit in enumerate(ideal_hits, start=1))

        ndcg = round(dcg / idcg, 4) if idcg > 0 else 0.0

        return SearchEvaluationMetrics(
            top_k=top_k,
            recall_at_k=recall,
            precision_at_k=precision,
            mrr=mrr,
            ndcg_at_k=ndcg,
        )

    @classmethod
    def evaluate_ann_vs_exact_recall(
        cls,
        ann_retrieved_ids: list[str],
        candidate_embeddings_map: dict[str, list[float]],
        query_embedding: list[float],
        top_k: int = 10,
    ) -> float:
        """
        Compare ANN (HNSW) retrieval candidate list against exact brute-force cosine distance ranking to measure HNSW recall loss percentage.
        """
        if not candidate_embeddings_map or not query_embedding:
            return 0.0

        exact_scored = []
        for cv_key, emb in candidate_embeddings_map.items():
            if emb and len(emb) == len(query_embedding):
                sim = EmbeddingService.cosine_similarity(query_embedding, emb)
                exact_scored.append((cv_key, sim))

        exact_scored.sort(key=lambda x: x[1], reverse=True)
        exact_top_k = [cv_key for cv_key, _ in exact_scored[:top_k]]

        exact_set = set(exact_top_k)
        ann_set = set(ann_retrieved_ids[:top_k])

        if not exact_set:
            return 0.0

        matched = len(exact_set & ann_set)
        recall_loss_pct = round((1.0 - (matched / len(exact_set))) * 100.0, 2)
        return recall_loss_pct
