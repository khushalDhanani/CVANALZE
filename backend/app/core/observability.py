from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings

logger = logging.getLogger("cv_analyzer")


@dataclass
class TelemetryEvent:
    event_type: str
    timestamp: float
    correlation_id: str
    data: dict[str, Any]


class ObservabilityEngine:
    """
    Enterprise Observability & Auditability Engine.
    Emits structured telemetry signals, tracks dashboard quality rates,
    maintains correlation IDs across execution boundaries, and fires production alerts.
    """

    _lock = threading.RLock()
    _events: list[TelemetryEvent] = []
    _max_event_history: int = 10000

    _counters: dict[str, int] = {
        "analysis_completed_total": 0,
        "analysis_degraded_total": 0,
        "requirement_assessed_total": 0,
        "requirement_failed_total": 0,
        "taxonomy_resolved_total": 0,
        "taxonomy_ambiguous_total": 0,
        "embedding_generated_total": 0,
        "embedding_cache_hits": 0,
        "embedding_errors": 0,
        "policy_loaded_total": 0,
        "policy_emergency_fallback_total": 0,
        "unassessable_components_total": 0,
        "assessable_components_total": 0,
    }

    _policy_versions: dict[str, int] = {}
    _active_alerts: list[dict[str, Any]] = []

    @classmethod
    def emit_signal(cls, event_type: str, correlation_id: str = "sys_corr", **kwargs: Any) -> None:
        """Emit one of the 6 canonical enterprise auditability signals."""
        now = time.time()
        event = TelemetryEvent(
            event_type=event_type,
            timestamp=now,
            correlation_id=correlation_id,
            data=dict(kwargs),
        )

        with cls._lock:
            cls._events.append(event)
            if len(cls._events) > cls._max_event_history:
                cls._events.pop(0)

            # Update specific signal counters & dashboard stats
            if event_type == "analysis.completed":
                cls._counters["analysis_completed_total"] += 1
                policy = kwargs.get("policy_snapshot", "unknown")
                cls._policy_versions[policy] = cls._policy_versions.get(policy, 0) + 1
                if kwargs.get("degraded_flags"):
                    cls._counters["analysis_degraded_total"] += 1

            elif event_type == "requirement.assessed":
                cls._counters["requirement_assessed_total"] += 1
                if kwargs.get("result_status") == "FAILED":
                    cls._counters["requirement_failed_total"] += 1

            elif event_type == "taxonomy.resolved":
                cls._counters["taxonomy_resolved_total"] += 1
                if kwargs.get("confidence", 1.0) < 0.70 or kwargs.get("fallback_used"):
                    cls._counters["taxonomy_ambiguous_total"] += 1

            elif event_type == "embedding.generated":
                cls._counters["embedding_generated_total"] += 1
                if kwargs.get("cache_hit"):
                    cls._counters["embedding_cache_hits"] += 1
                if kwargs.get("error_category"):
                    cls._counters["embedding_errors"] += 1

            elif event_type == "policy.loaded":
                cls._counters["policy_loaded_total"] += 1
                source = kwargs.get("source", "")
                if source in {"EMERGENCY_BUNDLED", "DEGRADED"}:
                    cls._counters["policy_emergency_fallback_total"] += 1
                    cls.trigger_alert(
                        alert_type="EMERGENCY_POLICY_USAGE",
                        severity="CRITICAL" if settings.IS_PRODUCTION else "WARNING",
                        message=f"Policy source '{source}' resolved for snapshot '{kwargs.get('policy_id')}'",
                    )

            elif event_type == "analysis.degraded":
                cls._counters["analysis_degraded_total"] += 1
                logger.warning(
                    f"[OBSERVABILITY_DEGRADED] corr={correlation_id} dep={kwargs.get('dependency')} reason={kwargs.get('reason')}"
                )

        logger.info(f"[TELEMETRY_SIGNAL] [{event_type}] corr={correlation_id} data={kwargs}")

    @classmethod
    def trigger_alert(cls, alert_type: str, severity: str, message: str) -> None:
        """Record production alert and log alert payload."""
        alert = {
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "timestamp": time.time(),
        }
        with cls._lock:
            cls._active_alerts.append(alert)
            if len(cls._active_alerts) > 100:
                cls._active_alerts.pop(0)
        logger.error(f"[ALERT_TRIGGERED] [{severity}] [{alert_type}] {message}")

    @classmethod
    def record_component_assessability(cls, assessability_map: dict[str, str]) -> None:
        """Record component assessability stats for unassessable rate calculation."""
        with cls._lock:
            for state in assessability_map.values():
                if state == "NOT_ASSESSABLE":
                    cls._counters["unassessable_components_total"] += 1
                else:
                    cls._counters["assessable_components_total"] += 1

    @classmethod
    def get_dashboard_report(cls) -> dict[str, Any]:
        """Generate comprehensive dashboards metrics & alert status report."""
        with cls._lock:
            total_analysis = cls._counters["analysis_completed_total"]
            degraded_analysis = cls._counters["analysis_degraded_total"]
            total_embed = cls._counters["embedding_generated_total"]
            embed_hits = cls._counters["embedding_cache_hits"]
            embed_errors = cls._counters["embedding_errors"]
            total_tax = cls._counters["taxonomy_resolved_total"]
            ambig_tax = cls._counters["taxonomy_ambiguous_total"]
            unassessable = cls._counters["unassessable_components_total"]
            assessable = cls._counters["assessable_components_total"]
            total_components = unassessable + assessable

            return {
                "metrics": {
                    "false_fallback_rate": round(degraded_analysis / total_analysis, 4) if total_analysis > 0 else 0.0,
                    "unassessable_rate": round(unassessable / total_components, 4) if total_components > 0 else 0.0,
                    "model_error_rate": round(embed_errors / total_embed, 4) if total_embed > 0 else 0.0,
                    "taxonomy_ambiguity_rate": round(ambig_tax / total_tax, 4) if total_tax > 0 else 0.0,
                    "cache_hit_rate": round(embed_hits / total_embed, 4) if total_embed > 0 else 0.0,
                    "policy_version_distribution": dict(cls._policy_versions),
                },
                "counters": dict(cls._counters),
                "active_alerts_count": len(cls._active_alerts),
                "active_alerts": list(cls._active_alerts[-10:]),
                "total_events_recorded": len(cls._events),
            }
