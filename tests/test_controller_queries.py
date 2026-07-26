from datetime import UTC, datetime
from pathlib import Path

from src.control.decision_engine import FallbackDecisionEngine
from src.control.models import ControllerRunMetadata
from src.storage.controller_queries import open_controller_read_only, rows
from src.storage.controller_store import ControllerStore

from tests.control_helpers import control_state, settings


def test_predefined_read_only_queries(tmp_path: Path) -> None:
    database = tmp_path / "controller.db"
    with ControllerStore(database, tmp_path) as store:
        store.begin_run(
            ControllerRunMetadata(
                "run", "sim", "shadow", datetime.now(UTC).isoformat(), "a", "b", 1
            )
        )
        store.append(
            *FallbackDecisionEngine("run", settings(), shadow=False).evaluate(control_state())[0]
        )
    with open_controller_read_only(database) as connection:
        assert len(rows(connection, "recent", "run")) == 1
        assert len(rows(connection, "zone", "run", value="space3_1")) == 1
