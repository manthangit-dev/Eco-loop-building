from pathlib import Path

import pytest
from src.storage.sqlite_store import DuplicateStateStorageError, SQLiteStateStore

from tests.state_helpers import completion, metadata, sample_state


def test_store_round_trip_and_integrity(tmp_path: Path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db", tmp_path)
    store.initialise_schema()
    store.begin_run(metadata())
    state = sample_state()
    store.append_state(state)
    latest = store.latest_state("test-run")
    assert latest is not None
    assert latest["fingerprint"] == state.fingerprint
    assert len(store.zone_history("test-run", "space1_1", 1, 10)) == 1
    store.finalise_run(completion())
    assert store.integrity_check() == "ok"
    assert store.foreign_key_check() == []
    store.close()


def test_store_rolls_back_duplicate_state(tmp_path: Path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db", tmp_path)
    store.initialise_schema()
    store.begin_run(metadata())
    state = sample_state()
    store.append_state(state)
    with pytest.raises(DuplicateStateStorageError):
        store.append_state(state)
    assert store.rollback_count == 1
    store.close()


def test_store_rejects_path_outside_approved_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        SQLiteStateStore(tmp_path.parent / "outside.db", tmp_path)
