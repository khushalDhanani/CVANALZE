from __future__ import annotations
import threading
from typing import Any


class CacheMetricsCollector:
    """Thread-safe per-namespace cache metrics collector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, int] = {}
        self._misses: dict[str, int] = {}
        self._sets: dict[str, int] = {}
        self._deletes: dict[str, int] = {}
        self._pattern_deletes: dict[str, int] = {}
        self._lookup_time_total_ms: dict[str, float] = {}
        self._lookup_count: dict[str, int] = {}
        self._save_time_total_ms: dict[str, float] = {}
        self._save_count: dict[str, int] = {}
        self._llm_calls_prevented: int = 0
        self._db_queries_prevented: int = 0
        self._refresh_count: dict[str, int] = {}

    # --- Per-namespace counters ---

    def record_hit(self, namespace: str) -> None:
        with self._lock:
            self._hits[namespace] = self._hits.get(namespace, 0) + 1

    def record_miss(self, namespace: str) -> None:
        with self._lock:
            self._misses[namespace] = self._misses.get(namespace, 0) + 1

    def record_set(self, namespace: str) -> None:
        with self._lock:
            self._sets[namespace] = self._sets.get(namespace, 0) + 1

    def record_delete(self, namespace: str) -> None:
        with self._lock:
            self._deletes[namespace] = self._deletes.get(namespace, 0) + 1

    def record_pattern_delete(self, namespace: str) -> None:
        with self._lock:
            self._pattern_deletes[namespace] = self._pattern_deletes.get(namespace, 0) + 1

    def record_lookup_time(self, namespace: str, elapsed_ms: float) -> None:
        with self._lock:
            self._lookup_time_total_ms[namespace] = self._lookup_time_total_ms.get(namespace, 0.0) + elapsed_ms
            self._lookup_count[namespace] = self._lookup_count.get(namespace, 0) + 1

    def record_save_time(self, namespace: str, elapsed_ms: float) -> None:
        with self._lock:
            self._save_time_total_ms[namespace] = self._save_time_total_ms.get(namespace, 0.0) + elapsed_ms
            self._save_count[namespace] = self._save_count.get(namespace, 0) + 1

    def record_refresh(self, namespace: str) -> None:
        with self._lock:
            self._refresh_count[namespace] = self._refresh_count.get(namespace, 0) + 1

    # --- Global counters ---

    def record_llm_call_prevented(self) -> None:
        with self._lock:
            self._llm_calls_prevented += 1

    def record_db_query_prevented(self) -> None:
        with self._lock:
            self._db_queries_prevented += 1

    # --- Report ---

    def report(self) -> dict[str, Any]:
        with self._lock:
            namespaces = set(self._hits) | set(self._misses) | set(self._sets)
            per_namespace: dict[str, dict[str, Any]] = {}
            total_hits = 0
            total_misses = 0
            for ns in sorted(namespaces):
                h = self._hits.get(ns, 0)
                m = self._misses.get(ns, 0)
                total_hits += h
                total_misses += m
                lookup_time = self._lookup_time_total_ms.get(ns, 0.0)
                lookup_n = self._lookup_count.get(ns, 0)
                save_time = self._save_time_total_ms.get(ns, 0.0)
                save_n = self._save_count.get(ns, 0)
                per_namespace[ns] = {
                    "hits": h,
                    "misses": m,
                    "hit_ratio": round(h / (h + m), 4) if (h + m) > 0 else 0.0,
                    "sets": self._sets.get(ns, 0),
                    "deletes": self._deletes.get(ns, 0),
                    "pattern_deletes": self._pattern_deletes.get(ns, 0),
                    "avg_lookup_time_ms": round(lookup_time / lookup_n, 2) if lookup_n > 0 else 0.0,
                    "avg_save_time_ms": round(save_time / save_n, 2) if save_n > 0 else 0.0,
                    "refresh_count": self._refresh_count.get(ns, 0),
                }

            return {
                "total_hits": total_hits,
                "total_misses": total_misses,
                "overall_hit_ratio": round(total_hits / (total_hits + total_misses), 4) if (total_hits + total_misses) > 0 else 0.0,
                "llm_calls_prevented": self._llm_calls_prevented,
                "db_queries_prevented": self._db_queries_prevented,
                "per_namespace": per_namespace,
            }

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._misses.clear()
            self._sets.clear()
            self._deletes.clear()
            self._pattern_deletes.clear()
            self._lookup_time_total_ms.clear()
            self._lookup_count.clear()
            self._save_time_total_ms.clear()
            self._save_count.clear()
            self._refresh_count.clear()
            self._llm_calls_prevented = 0
            self._db_queries_prevented = 0


# Module-level singleton
_metrics = CacheMetricsCollector()
