from __future__ import annotations

from app.core.observability import ObservabilityEngine


def test_emit_signals_all_six_types() -> None:
    """Workstream 5.4: ObservabilityEngine records all 6 canonical telemetry signals."""
    corr_id = "corr_test_999"

    # 1. analysis.completed
    ObservabilityEngine.emit_signal(
        "analysis.completed",
        correlation_id=corr_id,
        candidate_id="cand_1",
        vacancy_id="vac_1",
        policy_snapshot="snap_v1",
        taxonomy_version="v3.0",
        duration=150.0,
    )

    # 2. requirement.assessed
    ObservabilityEngine.emit_signal(
        "requirement.assessed",
        correlation_id=corr_id,
        requirement_type="MANDATORY",
        result_status="SATISFIED",
        evidence_count=3,
    )

    # 3. taxonomy.resolved
    ObservabilityEngine.emit_signal(
        "taxonomy.resolved",
        correlation_id=corr_id,
        source="dynamic",
        confidence=0.85,
        fallback_used=False,
    )

    # 4. embedding.generated
    ObservabilityEngine.emit_signal(
        "embedding.generated",
        correlation_id=corr_id,
        model="nomic-embed-text",
        dimension=768,
        cache_hit=True,
        latency=12.5,
    )

    # 5. policy.loaded
    ObservabilityEngine.emit_signal(
        "policy.loaded",
        correlation_id=corr_id,
        policy_id="snap_v1",
        source="DATABASE",
    )

    # 6. analysis.degraded
    ObservabilityEngine.emit_signal(
        "analysis.degraded",
        correlation_id=corr_id,
        dependency="OllamaLLM",
        reason="Timeout",
        user_visible_impact="LLM_UNAVAILABLE_FALLBACK",
    )

    report = ObservabilityEngine.get_dashboard_report()
    assert report["total_events_recorded"] >= 6
    assert report["counters"]["analysis_completed_total"] >= 1
    assert report["counters"]["requirement_assessed_total"] >= 1
    assert report["counters"]["taxonomy_resolved_total"] >= 1
    assert report["counters"]["embedding_generated_total"] >= 1
    assert report["counters"]["policy_loaded_total"] >= 1


def test_dashboard_rates_calculations() -> None:
    """Workstream 5.4: Dashboard calculates quality rates (fallback, unassessable, error, ambiguity, cache hit)."""
    ObservabilityEngine.record_component_assessability({"role": "VERIFIED", "domain": "NOT_ASSESSABLE"})

    report = ObservabilityEngine.get_dashboard_report()
    metrics = report["metrics"]

    assert "false_fallback_rate" in metrics
    assert "unassessable_rate" in metrics
    assert "model_error_rate" in metrics
    assert "taxonomy_ambiguity_rate" in metrics
    assert "cache_hit_rate" in metrics
    assert "policy_version_distribution" in metrics

    assert 0.0 <= metrics["unassessable_rate"] <= 1.0


def test_emergency_policy_alert_trigger() -> None:
    """Workstream 5.4: Emergency/bundled policy resolution triggers CRITICAL/WARNING alert."""
    ObservabilityEngine.emit_signal(
        "policy.loaded",
        correlation_id="corr_alert_test",
        policy_id="snap_emergency_bundled",
        source="EMERGENCY_BUNDLED",
    )

    report = ObservabilityEngine.get_dashboard_report()
    assert report["active_alerts_count"] >= 1
    alerts = report["active_alerts"]
    assert any(a["alert_type"] == "EMERGENCY_POLICY_USAGE" for a in alerts)
