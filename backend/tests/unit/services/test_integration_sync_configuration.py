from __future__ import annotations

from datetime import datetime, timedelta, timezone
from inspect import getsource
from types import SimpleNamespace
from unittest.mock import patch

from app.core.config import settings
from app.services.integration_sync_service import BaseSyncService, SourceFreshnessService


def test_source_freshness_uses_runtime_max_age(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SOURCE_FRESHNESS_MAX_AGE_SECONDS", 30, raising=False)
    watermark = SimpleNamespace(
        synced_at=datetime.now(timezone.utc) - timedelta(seconds=45),
    )

    with patch("app.services.integration_sync_service.PostgresAppSession") as session_factory:
        session = session_factory.return_value.__enter__.return_value
        session.query.return_value.filter.return_value.first.return_value = watermark
        result = SourceFreshnessService.check_freshness("candidate")

    assert result["status"] == "STALE_SOURCE"


def test_sync_batches_use_runtime_setting() -> None:
    source = getsource(BaseSyncService.run_sync)

    assert "settings.INTEGRATION_SYNC_BATCH_SIZE" in source
    assert "yield_per(1000)" not in source
    assert "batch_size = 1000" not in source
