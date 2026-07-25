import csv
import json
from pathlib import Path

import pytest
from src.energyplus.sensor_writers import SensorWriters

from tests.test_sensor_snapshot import snapshot


def test_writers_stream_utf8_jsonl_and_csv_atomically(tmp_path: Path) -> None:
    output = tmp_path / "current"
    writers = SensorWriters(output, tmp_path, "rows.jsonl", "rows.csv", ("Z",), ("fans",), 1)
    writers.write(snapshot())
    assert not (output / "rows.jsonl").exists()
    writers.close()
    writers.close()
    assert json.loads((output / "rows.jsonl").read_text(encoding="utf-8"))["sequence"] == 1
    with (output / "rows.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["meter.fans.raw_j"] == ""
    with pytest.raises(RuntimeError, match="closed"):
        writers.write(snapshot())


def test_writers_reject_approved_root_as_output(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="child"):
        SensorWriters(tmp_path, tmp_path, "a", "b", (), (), 1)

