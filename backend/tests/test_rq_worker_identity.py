from unittest.mock import patch

import pytest

from app.core.rq_worker_identity import build_rq_worker_name


def test_worker_name_combines_stable_role_with_unique_process_identity():
    with patch("app.core.rq_worker_identity.uuid4") as uuid4:
        uuid4.return_value.hex = "0123456789abcdef"

        worker_name = build_rq_worker_name(" cv-analyzer auxiliary-worker ")

    assert worker_name == "cv-analyzer-auxiliary-worker-0123456789abcdef"


def test_worker_name_rejects_empty_role():
    with pytest.raises(ValueError, match="must not be empty"):
        build_rq_worker_name("   ")
