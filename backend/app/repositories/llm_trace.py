from __future__ import annotations

import json
import threading
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.core.database import PostgresAppSession
from app.core.logging import logger
from app.models.llm_trace import LLMExecutionTraceRecord
from app.schemas.llm_trace import LLMExecutionTrace

_FORBIDDEN_METADATA_KEYS = {"prompt", "raw_prompt", "raw_response", "reasoning", "cv_text", "text", "content", "email", "phone"}


class LLMTraceMetrics:
    _lock = threading.Lock()
    _counts: Counter[str] = Counter()
    _duration_ms: defaultdict[str, float] = defaultdict(float)
    _latencies: defaultdict[str, deque[float]] = defaultdict(lambda: deque(maxlen=2000))
    _input_tokens = 0
    _output_tokens = 0

    @classmethod
    def record(cls, trace: LLMExecutionTrace) -> None:
        with cls._lock:
            cls._counts["total"] += 1
            cls._counts[f"operation:{trace.operation}"] += 1
            cls._counts[f"cache:{trace.cache_status}"] += 1
            cls._counts[f"validation:{trace.validation_status}"] += 1
            if trace.fallback_used:
                cls._counts["fallbacks"] += 1
            if trace.error_class:
                cls._counts["errors"] += 1
                cls._counts[f"error:{trace.error_class}"] += 1
            if "Timeout" in trace.error_class:
                cls._counts["timeouts"] += 1
            cls._duration_ms[trace.operation] += trace.duration_ms
            cls._latencies[trace.operation].append(trace.duration_ms)
            cls._input_tokens += trace.input_tokens
            cls._output_tokens += trace.output_tokens

    @classmethod
    def report(cls) -> dict[str, Any]:
        with cls._lock:
            operations: dict[str, Any] = {}
            for key, count in cls._counts.items():
                if not key.startswith("operation:"):
                    continue
                operation = key.split(":", 1)[1]
                operations[operation] = {
                    "requests": count,
                    "average_duration_ms": round(cls._duration_ms[operation] / count, 2) if count else 0.0,
                    "p50_duration_ms": cls._percentile(cls._latencies[operation], 0.50),
                    "p95_duration_ms": cls._percentile(cls._latencies[operation], 0.95),
                    "p99_duration_ms": cls._percentile(cls._latencies[operation], 0.99),
                }
            total = cls._counts["total"]
            validated = cls._counts["validation:VALID"] + cls._counts["validation:INVALID"]
            return {
                "requests": total,
                "fallbacks": cls._counts["fallbacks"],
                "timeouts": cls._counts["timeouts"],
                "errors": cls._counts["errors"],
                "input_tokens": cls._input_tokens,
                "output_tokens": cls._output_tokens,
                "schema_valid": cls._counts["validation:VALID"],
                "schema_invalid": cls._counts["validation:INVALID"],
                "schema_validity_rate": round(cls._counts["validation:VALID"] / validated, 4) if validated else 1.0,
                "fallback_rate": round(cls._counts["fallbacks"] / total, 4) if total else 0.0,
                "timeout_rate": round(cls._counts["timeouts"] / total, 4) if total else 0.0,
                "cache_hits": cls._counts["cache:HIT"],
                "operations": operations,
            }

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._counts.clear()
            cls._duration_ms.clear()
            cls._latencies.clear()
            cls._input_tokens = 0
            cls._output_tokens = 0

    @staticmethod
    def _percentile(values: deque[float], quantile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
        return round(ordered[index], 2)


class LLMTraceRepository:
    @classmethod
    def save(cls, trace: LLMExecutionTrace) -> bool:
        if not settings.LLM_TRACE_ENABLED:
            return False
        sanitized = trace.model_copy(update={"quality_metadata": cls._sanitize_metadata(trace.quality_metadata)})
        LLMTraceMetrics.record(sanitized)
        if PostgresAppSession is None:
            return False
        try:
            with PostgresAppSession() as db:
                db.add(LLMExecutionTraceRecord(**sanitized.model_dump(exclude={"created_at"})))
                db.commit()
            return True
        except Exception as exc:
            logger.warning(f"[LLM_TRACE] status=PERSISTENCE_FALLBACK error={type(exc).__name__}")
            return False

    @classmethod
    def purge_expired(cls) -> int:
        if PostgresAppSession is None:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, settings.LLM_TRACE_RETENTION_DAYS))
        try:
            with PostgresAppSession() as db:
                deleted = db.query(LLMExecutionTraceRecord).filter(LLMExecutionTraceRecord.created_at < cutoff).delete(synchronize_session=False)
                db.commit()
                return int(deleted or 0)
        except Exception as exc:
            logger.warning(f"[LLM_TRACE] status=RETENTION_FAILED error={type(exc).__name__}")
            return 0

    @classmethod
    def _sanitize_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in _FORBIDDEN_METADATA_KEYS:
                continue
            if isinstance(item, (str, int, float, bool)) or item is None:
                sanitized[str(key)[:80]] = item if not isinstance(item, str) else item[:256]
            elif isinstance(item, list):
                sanitized[str(key)[:80]] = [entry for entry in item[:50] if isinstance(entry, (str, int, float, bool))]
            elif isinstance(item, dict):
                sanitized[str(key)[:80]] = cls._sanitize_metadata(item)
        json.dumps(sanitized)
        return sanitized
