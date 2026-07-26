import sqlite3
from pathlib import Path

from src.storage.llm_schema import migrate_llm_schema


def test_schema_five_is_idempotent_and_has_foreign_keys(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "llm.db")
    migrate_llm_schema(connection)
    migrate_llm_schema(connection)
    assert (
        connection.execute(
            "SELECT value FROM schema_metadata WHERE key='schema_version'"
        ).fetchone()[0]
        == "5"
    )
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    connection.close()
