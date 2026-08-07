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
    ):
        start_worker.main()

    worker_class.assert_called_once()
    worker.work.assert_called_once_with()
