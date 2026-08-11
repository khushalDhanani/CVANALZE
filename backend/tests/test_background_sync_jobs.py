import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core import background_tasks
from app.core.config import settings
from rq.cron import CronScheduler
from start_scheduler import ResilientCronScheduler, register_recurring_jobs


class _FakeScheduler:
    def __init__(self):
        self.registrations = []

    def register(self, function, **options):
        self.registrations.append((function, options))


def test_scheduler_ignores_redis_disconnect_while_registering_death(monkeypatch):
    scheduler = object.__new__(ResilientCronScheduler)
    monkeypatch.setattr(
        CronScheduler,
        "register_death",
        lambda _self, _pipeline=None: (_ for _ in ()).throw(RedisConnectionError("offline")),
    )

    scheduler.register_death()


def test_scheduler_preserves_unexpected_register_death_errors(monkeypatch):
    scheduler = object.__new__(ResilientCronScheduler)
    monkeypatch.setattr(
        CronScheduler,
        "register_death",
        lambda _self, _pipeline=None: (_ for _ in ()).throw(RuntimeError("unexpected")),
    )

    with pytest.raises(RuntimeError, match="unexpected"):
        scheduler.register_death()


def test_scheduler_registers_reconciliation_sync_and_validation_snapshot_jobs(monkeypatch):
    monkeypatch.setattr(settings, "CV_JOB_RECONCILIATION_INTERVAL_SECONDS", 60)
    monkeypatch.setattr(settings, "BACKGROUND_SYNC_ENABLED", True)
    monkeypatch.setattr(settings, "VALIDATION_METRICS_SNAPSHOT_ENABLED", True)
    scheduler = _FakeScheduler()

    assert register_recurring_jobs(scheduler) == 3
    assert [registration[0] for registration in scheduler.registrations] == [
        background_tasks.reconcile_cv_processing_jobs,
        background_tasks.run_integration_sync,
        background_tasks.snapshot_validation_metrics,
    ]
    assert scheduler.registrations[0][1]["queue_name"] == settings.RQ_AUXILIARY_QUEUE_NAME
    assert scheduler.registrations[1][1]["queue_name"] == settings.RQ_AUXILIARY_QUEUE_NAME
    assert scheduler.registrations[2][1]["queue_name"] == settings.RQ_SHADOW_QUEUE_NAME


def test_canonical_sync_runs_all_snapshot_services(monkeypatch):
    from app.services.integration_sync_service import CandidateSyncService, ReferenceSyncService, VacancySyncService

    calls = []
    monkeypatch.setattr(background_tasks, "_run_with_lock", lambda _key, task: task())
    monkeypatch.setattr(
        ReferenceSyncService,
        "sync_all",
        lambda: calls.append("references") or {"departments": {"status": "completed"}},
    )
    monkeypatch.setattr(CandidateSyncService, "run_sync", lambda: calls.append("candidates") or {"status": "completed"})
    monkeypatch.setattr(VacancySyncService, "run_sync", lambda: calls.append("vacancies") or {"status": "completed"})

    result = background_tasks.run_integration_sync()

    assert calls == ["references", "candidates", "vacancies"]
    assert result["status"] == "completed"


def test_canonical_sync_surfaces_an_unavailable_entity(monkeypatch):
    from app.services.integration_sync_service import CandidateSyncService, ReferenceSyncService, VacancySyncService

    monkeypatch.setattr(background_tasks, "_run_with_lock", lambda _key, task: task())
    monkeypatch.setattr(ReferenceSyncService, "sync_all", lambda: {"departments": {"status": "completed"}})
    monkeypatch.setattr(CandidateSyncService, "run_sync", lambda: {"status": "skipped"})
    monkeypatch.setattr(VacancySyncService, "run_sync", lambda: {"status": "completed"})

    try:
        background_tasks.run_integration_sync()
    except RuntimeError as exc:
        assert "candidates" in str(exc)
    else:
        raise AssertionError("Expected an unavailable canonical sync entity to fail the RQ job")


def test_validation_snapshot_job_uses_existing_metrics_engine(monkeypatch):
    from app.services.shadow_validation_service import MetricsEngine

    calls = []
    monkeypatch.setattr(MetricsEngine, "snapshot_metrics", lambda: calls.append("snapshot"))

    assert background_tasks.snapshot_validation_metrics() == {"status": "completed"}
    assert calls == ["snapshot"]
