from app.core import background_tasks
from app.core.config import settings
from start_scheduler import register_recurring_jobs


class _FakeScheduler:
    def __init__(self):
        self.registrations = []

    def register(self, function, **options):
        self.registrations.append((function, options))


def test_scheduler_registers_sync_and_validation_snapshot_jobs(monkeypatch):
    monkeypatch.setattr(settings, "BACKGROUND_SYNC_ENABLED", True)
    monkeypatch.setattr(settings, "VALIDATION_METRICS_SNAPSHOT_ENABLED", True)
    scheduler = _FakeScheduler()

    assert register_recurring_jobs(scheduler) == 2
    assert [registration[0] for registration in scheduler.registrations] == [
        background_tasks.run_integration_sync,
        background_tasks.snapshot_validation_metrics,
    ]
    assert scheduler.registrations[0][1]["queue_name"] == settings.RQ_QUEUE_NAME
    assert scheduler.registrations[1][1]["queue_name"] == "shadow_validation"


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
