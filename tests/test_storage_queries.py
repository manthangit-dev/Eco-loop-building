from pathlib import Path

from src.storage.queries import open_read_only, rows_as_dicts, table_counts
from src.storage.sqlite_store import SQLiteStateStore

from tests.state_helpers import metadata, sample_state


def test_read_only_queries_return_expected_rows(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    store = SQLiteStateStore(database, tmp_path)
    store.initialise_schema()
    store.begin_run(metadata())
    store.append_state(sample_state())
    store.close()
    with open_read_only(database) as connection:
        assert table_counts(connection)["building_states"] == 1
        rows = connection.execute("SELECT sequence FROM building_states").fetchall()
        assert rows_as_dicts(rows) == [{"sequence": 1}]
