import os
from unittest.mock import Mock, patch

import pytest

os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

import start_worker


def test_worker_uses_one_isolated_rq_worker_for_the_cv_queue():
    redis_connection = Mock()
    worker = Mock()

    with (
        patch.object(start_worker.Redis, "from_url", return_value=redis_connection),
        patch.object(start_worker, "Queue", side_effect=lambda name, connection: (name, connection)),
        patch.object(start_worker, "Worker", return_value=worker) as worker_class,
        patch.object(start_worker.settings, "CV_PROCESSING_CONCURRENCY", 1),
        patch.object(start_worker.settings, "RQ_WORKER_MAX_JOBS", 0),
    ):
        start_worker.main()

    worker_class.assert_called_once()
    assert worker_class.call_args.args[0] == [(start_worker.settings.RQ_QUEUE_NAME, redis_connection)]
    assert worker_class.call_args.kwargs["name"] == "cv-processing-worker-1"
    assert worker_class.call_args.kwargs["work_horse_killed_handler"] is start_worker.handle_work_horse_killed
    worker.work.assert_called_once_with(with_scheduler=True, maintenance_interval=start_worker.settings.RQ_MAINTENANCE_INTERVAL_SECONDS)


def test_worker_refuses_parallel_cv_concurrency_configuration():
    with patch.object(start_worker.settings, "CV_PROCESSING_CONCURRENCY", 2):
        with pytest.raises(RuntimeError, match="must be 1"):
            start_worker.main()


def test_worker_forwards_configured_recycle_limit():
    worker = Mock()

    with (
        patch.object(start_worker.Redis, "from_url"),
        patch.object(start_worker, "Queue"),
        patch.object(start_worker, "Worker", return_value=worker),
        patch.object(start_worker.settings, "CV_PROCESSING_CONCURRENCY", 1),
        patch.object(start_worker.settings, "RQ_WORKER_MAX_JOBS", 10),
    ):
        start_worker.main()

    worker.work.assert_called_once_with(
        with_scheduler=True,
        maintenance_interval=start_worker.settings.RQ_MAINTENANCE_INTERVAL_SECONDS,
        max_jobs=10,
    )
