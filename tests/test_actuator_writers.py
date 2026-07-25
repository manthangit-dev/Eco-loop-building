import csv
from pathlib import Path

import pytest
from src.energyplus.actuator_events import ActuatorEvent, ActuatorEventType
from src.energyplus.actuator_writers import ActuatorWriters


def event() -> ActuatorEvent:
    return ActuatorEvent(
        1,
        "07-19 14:15",
        ActuatorEventType.OVERRIDE_APPLIED,
        "intervention",
        "SPACE3-1",
        "Zone Temperature Control",
        "Cooling Setpoint",
        "SPACE3-1",
        42,
        23.9,
        24.9,
        24.9,
        24.9,
        11.0,
        False,
        "Δ",
    )


def test_writer_streams_utf8_jsonl_and_csv(tmp_path: Path) -> None:
    writer = ActuatorWriters(tmp_path / "run", tmp_path, "events.jsonl", "events.csv")
    writer.write(event())
    writer.close()
    assert "Δ" in (tmp_path / "run/events.jsonl").read_text(encoding="utf-8")
    with (tmp_path / "run/events.csv").open(encoding="utf-8", newline="") as stream:
        assert next(csv.DictReader(stream))["event_type"] == "OVERRIDE_APPLIED"


def test_writer_rejects_root_output(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="below"):
        ActuatorWriters(tmp_path, tmp_path, "a.jsonl", "a.csv")
