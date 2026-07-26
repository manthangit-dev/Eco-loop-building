import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from src.control.decision_engine import FallbackDecisionEngine
from src.control.models import ControllerRunMetadata
from src.storage.controller_store import ControllerStore

from tests.control_helpers import control_state, settings


def test_store_run_decision_command_and_foreign_keys(tmp_path: Path) -> None:
    store = ControllerStore(tmp_path / "controller.db", tmp_path)
    store.begin_run(
        ControllerRunMetadata(
            "run", "sim", "shadow", datetime.now(UTC).isoformat(), "a" * 64, "b" * 64, 1
        )
    )
    decision, command = FallbackDecisionEngine("run", settings(), shadow=False).evaluate(
        control_state()
    )[0]
    store.append(decision, command)
    assert store.counts()["control_decisions"] == 1
    with pytest.raises(sqlite3.IntegrityError):
        store.append(decision, command)
    assert store.connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert store.connection.execute("PRAGMA foreign_key_check").fetchall() == []
    store.close()
