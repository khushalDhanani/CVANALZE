from unittest.mock import MagicMock, Mock

import pytest

from app.core import database, lifecycle
from app.core.config import Settings


@pytest.fixture
def mssql_startup_guard(monkeypatch):
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = Mock()
    test_logger = Mock()
    monkeypatch.setattr(database, "mssql_read_engine", engine)
    monkeypatch.setattr(lifecycle, "logger", test_logger)
    return test_logger


def test_readonly_credential_allows_startup(monkeypatch, mssql_startup_guard):
    monkeypatch.setattr(lifecycle.settings, "MSSQL_READONLY_ENFORCEMENT", True)
    monkeypatch.setattr(lifecycle, "_find_mssql_write_permissions", lambda _conn, _text: set())

    lifecycle.verify_mssql_readonly()

    mssql_startup_guard.info.assert_called_once_with("[STARTUP] MSSQL credential verified as read-only.")


def test_write_enabled_credential_fails_when_enforcement_is_enabled(monkeypatch, mssql_startup_guard):
    monkeypatch.setattr(lifecycle.settings, "MSSQL_READONLY_ENFORCEMENT", True)
    monkeypatch.setattr(lifecycle, "_find_mssql_write_permissions", lambda _conn, _text: {"UPDATE", "CONTROL"})

    with pytest.raises(RuntimeError, match=r"CONTROL, UPDATE"):
        lifecycle.verify_mssql_readonly()

    error_message = mssql_startup_guard.error.call_args.args[1]
    assert "CONTROL, UPDATE" in error_message
    assert "password" not in error_message.lower()


def test_write_enabled_credential_warns_when_local_enforcement_is_disabled(monkeypatch, mssql_startup_guard):
    monkeypatch.setattr(lifecycle.settings, "MSSQL_READONLY_ENFORCEMENT", False)
    monkeypatch.setattr(lifecycle, "_find_mssql_write_permissions", lambda _conn, _text: {"INSERT"})

    lifecycle.verify_mssql_readonly()

    warning_message = mssql_startup_guard.warning.call_args.args[1]
    assert "INSERT" in warning_message
    assert "dedicated credential" in warning_message


def test_permission_audit_failure_fails_closed_when_enforced(monkeypatch, mssql_startup_guard):
    monkeypatch.setattr(lifecycle.settings, "MSSQL_READONLY_ENFORCEMENT", True)

    def fail_audit(_conn, _text):
        raise ConnectionError("sensitive connection details")

    monkeypatch.setattr(lifecycle, "_find_mssql_write_permissions", fail_audit)

    with pytest.raises(RuntimeError, match=r"ConnectionError") as exc_info:
        lifecycle.verify_mssql_readonly()

    assert "sensitive connection details" not in str(exc_info.value)


def test_production_rejects_disabled_mssql_enforcement():
    with pytest.raises(ValueError, match="MSSQL_READONLY_ENFORCEMENT must be true"):
        Settings(
            _env_file=None,
            APP_ENVIRONMENT="production",
            MSSQL_READONLY_ENFORCEMENT=False,
            MSSQL_READ_ONLY_URL="mssql+pyodbc://readonly:secret@sql.example/enterprise",
            POSTGRES_APP_URL="postgresql://app:secret@postgres.example/app",
            REDIS_URL="redis://redis.example/0",
        )


def test_permission_classifier_detects_implied_and_scoped_write_access():
    connection = Mock()
    connection.execute.side_effect = [
        [("CONNECT",), ("CONTROL",), ("SELECT",), ("ALTER ANY ROLE",)],
        [("CONNECT SQL",)],
    ]

    permissions = lifecycle._find_mssql_write_permissions(connection, lambda query: query)

    assert permissions == {"CONTROL"}
    assert connection.execute.call_count == 2
