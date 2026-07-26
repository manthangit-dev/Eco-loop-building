import sqlite3
from pathlib import Path

from src.safety.guard import SafetyGuard
from src.storage.safety_schema import migrate_safety_schema
from src.storage.safety_store import SafetyStore

from tests.safety_helpers import memory, proposal, safety_settings


def test_schema_migration_is_idempotent_and_foreign_keys_hold(tmp_path: Path) -> None:
    database = tmp_path / "guard.db"
    connection = sqlite3.connect(database)
    migrate_safety_schema(connection)
    migrate_safety_schema(connection)
    assert (
        connection.execute(
            "SELECT value FROM schema_metadata WHERE key='schema_version'"
        ).fetchone()[0]
        == "3"
    )
    connection.close()
    with SafetyStore(database, tmp_path) as store:
        decision, command = SafetyGuard(safety_settings(), memory()).evaluate(proposal())
        store.append(decision, command)
        assert store.connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert store.connection.execute("PRAGMA foreign_key_check").fetchall() == []
