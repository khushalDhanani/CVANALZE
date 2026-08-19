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
        patch.object(start_worker, "RuntimeDependencyWorker", return_value=worker) as worker_class,
        patch.object(start_worker, "build_rq_worker_name", return_value="cv-worker-unique") as worker_name,
        patch.object(start_worker, "wait_for_cv_runtime_dependencies") as wait_for_dependencies,
        patch.object(start_worker.settings, "CV_PROCESSING_CONCURRENCY", 1),
        patch.object(start_worker.settings, "RQ_WORKER_MAX_JOBS", 0),
    ):
        start_worker.main()

    worker_class.assert_called_once()
    wait_for_dependencies.assert_called_once_with(process_name="CV_WORKER")
    assert worker_class.call_args.args[0] == [(start_worker.settings.RQ_QUEUE_NAME, redis_connection)]
    worker_name.assert_called_once_with(f"{start_worker.settings.RQ_QUEUE_NAME}-worker")
    assert worker_class.call_args.kwargs["name"] == "cv-worker-unique"
    assert worker_class.call_args.kwargs["maintenance_interval"] == start_worker.settings.RQ_MAINTENANCE_INTERVAL_SECONDS
    assert worker_class.call_args.kwargs["work_horse_killed_handler"] is start_worker.handle_work_horse_killed
    worker.work.assert_called_once_with(with_scheduler=True)


def test_worker_refuses_parallel_cv_concurrency_configuration():
    with patch.object(start_worker.settings, "CV_PROCESSING_CONCURRENCY", 2):
        with pytest.raises(RuntimeError, match="must be 1"):
            start_worker.main()


def test_worker_forwards_configured_recycle_limit():
    worker = Mock()

    with (
        patch.object(start_worker.Redis, "from_url"),
        patch.object(start_worker, "Queue"),
        patch.object(start_worker, "RuntimeDependencyWorker", return_value=worker),
        patch.object(start_worker, "wait_for_cv_runtime_dependencies"),
        patch.object(start_worker.settings, "CV_PROCESSING_CONCURRENCY", 1),
        patch.object(start_worker.settings, "RQ_WORKER_MAX_JOBS", 10),
    ):
        start_worker.main()

    worker.work.assert_called_once_with(
        with_scheduler=True,
        max_jobs=10,
    )


def test_worker_checks_runtime_dependencies_before_each_dequeue():
    worker = start_worker.RuntimeDependencyWorker.__new__(start_worker.RuntimeDependencyWorker)

    with (
        patch.object(start_worker, "wait_for_cv_runtime_dependencies") as wait_for_dependencies,
        patch.object(start_worker, "cv_runtime_readiness", return_value=start_worker.RUNTIME_READY),
        patch.object(start_worker.Worker, "dequeue_job_and_maintain_ttl", return_value=("job", "queue")) as dequeue,
    ):
        result = worker.dequeue_job_and_maintain_ttl(5, 10)

    wait_for_dependencies.assert_called_once()
    assert wait_for_dependencies.call_args.kwargs["process_name"] == "CV_WORKER"
    assert wait_for_dependencies.call_args.kwargs["on_wait"].__self__ is worker
    dequeue.assert_called_once_with(5, 10)
    assert result == ("job", "queue")


def test_worker_restores_raced_job_to_fifo_front_when_prompt_becomes_unready():
    worker = start_worker.RuntimeDependencyWorker.__new__(start_worker.RuntimeDependencyWorker)
    pipeline = Mock()
    connection = Mock()
    connection.pipeline.return_value = pipeline
    worker.connection = connection
    first_job = Mock(id="job-1")
    second_job = Mock(id="job-1")
    queue = Mock(key="rq:queue:cv-processing")

    with (
        patch.object(start_worker, "wait_for_cv_runtime_dependencies"),
        patch.object(
            start_worker,
            "cv_runtime_readiness",
            side_effect=["PROMPT_NOT_READY", start_worker.RUNTIME_READY],
        ),
        patch.object(
            start_worker.Worker,
            "dequeue_job_and_maintain_ttl",
            side_effect=[(first_job, queue), (second_job, queue)],
        ),
    ):
        result = worker.dequeue_job_and_maintain_ttl(5)

    pipeline.lrem.assert_called_once_with("rq:queue:cv-processing:intermediate", 1, "job-1")
    pipeline.lpush.assert_called_once_with("rq:queue:cv-processing", "job-1")
    pipeline.execute.assert_called_once_with()
    assert result == (second_job, queue)
