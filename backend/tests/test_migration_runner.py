from unittest.mock import MagicMock

from scripts.run_migrations import execute_migration_sql


def test_migration_sql_executes_json_literals_without_bind_parameter_parsing():
    connection = MagicMock()
    content = "INSERT INTO policies (config) VALUES ('{\"enabled\":true,\"manual_review\":false}');"

    execute_migration_sql(connection, content)

    connection.exec_driver_sql.assert_called_once_with(content)
    connection.execute.assert_not_called()
