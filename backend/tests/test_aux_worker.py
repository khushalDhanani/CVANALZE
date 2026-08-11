from unittest.mock import Mock, patch

import start_aux_worker


def test_auxiliary_worker_never_subscribes_to_cv_processing_queue():
    worker = Mock()

    with (
        patch.object(start_aux_worker.Redis, "from_url"),
        patch.object(start_aux_worker, "Worker", return_value=worker) as worker_class,
        patch.object(start_aux_worker.RuleConfigManager, "load_config"),
        patch.object(start_aux_worker, "start_config_invalidation_listener"),
    ):
        start_aux_worker.main()

    queues = worker_class.call_args.args[0]
    assert [queue.name for queue in queues] == [
        start_aux_worker.settings.RQ_AUXILIARY_QUEUE_NAME,
        start_aux_worker.settings.RQ_SHADOW_QUEUE_NAME,
    ]
    assert start_aux_worker.settings.RQ_QUEUE_NAME not in [queue.name for queue in queues]
    worker.work.assert_called_once_with(
        with_scheduler=True,
        maintenance_interval=start_aux_worker.settings.RQ_MAINTENANCE_INTERVAL_SECONDS,
    )
