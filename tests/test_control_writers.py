from datetime import UTC, datetime
from pathlib import Path

from src.control.decision_engine import FallbackDecisionEngine
from src.control.models import ControllerRunMetadata
from src.control.writers import ControllerWriter

from tests.control_helpers import control_state, settings


def test_bounded_writer_persists_and_drains(tmp_path: Path) -> None:
    metadata = ControllerRunMetadata(
        "run", "sim", "shadow", datetime.now(UTC).isoformat(), "a" * 64, "b" * 64, 1
    )
    writer = ControllerWriter(tmp_path / "controller.db", tmp_path, metadata, capacity=2)
    writer.start()
    decision, command = FallbackDecisionEngine("run", settings(), shadow=False).evaluate(
        control_state()
    )[0]
    writer.enqueue(decision, command)
    writer.stop()
    assert writer.persisted_decisions == 1
