import os
from unittest.mock import Mock, patch

os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

import start_worker


def test_worker_executes_jobs_in_process_for_normal_resource_cleanup():
    redis_connection = Mock()
    worker = Mock()

    with (
        patch.object(start_worker.Redis, "from_url", return_value=redis_connection),
        patch.object(start_worker, "Queue", side_effect=lambda name, connection: (name, connection)),
        patch.object(start_worker, "SimpleWorker", return_value=worker) as worker_class,
        patch.object(start_worker.settings, "RQ_WORKER_MAX_JOBS", 0),
    ):
        start_worker.main()

    worker_class.assert_called_once()
    worker.work.assert_called_once_with(with_scheduler=True)


def test_worker_forwards_configured_recycle_limit():
    worker = Mock()

    with (
        patch.object(start_worker.Redis, "from_url"),
        patch.object(start_worker, "Queue"),
        patch.object(start_worker, "SimpleWorker", return_value=worker),
        patch.object(start_worker.settings, "RQ_WORKER_MAX_JOBS", 10),
    ):
        start_worker.main()

    worker.work.assert_called_once_with(with_scheduler=True, max_jobs=10)
