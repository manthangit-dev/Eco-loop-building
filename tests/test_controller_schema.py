import sqlite3

import pytest
from src.storage.controller_schema import migrate_controller_schema


def test_migration_is_idempotent_and_rejects_future() -> None:
    connection = sqlite3.connect(":memory:")
    migrate_controller_schema(connection)
    migrate_controller_schema(connection)
    assert connection.execute("SELECT value FROM schema_metadata").fetchone()[0] == "2"
    connection.execute("UPDATE schema_metadata SET value='3'")
    with pytest.raises(ValueError):
        migrate_controller_schema(connection)
