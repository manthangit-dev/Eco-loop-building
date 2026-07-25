from pathlib import Path

from src.storage.schema import SCHEMA_SQL, SCHEMA_VERSION
from src.storage.sqlite_store import SQLiteStateStore


def test_schema_version_and_required_tables(tmp_path: Path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db", tmp_path)
    store.initialise_schema()
    tables = {
        row[0]
        for row in store.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    store.close()
    assert SCHEMA_VERSION == 1
    assert {"simulation_runs", "building_states", "zone_states"} <= tables
    assert "FOREIGN KEY" not in SCHEMA_SQL  # References express the enforced FKs.
