import json
import math

import pytest
from src.energyplus.sensor_snapshot import (
    BuildingSensorState,
    OutdoorSensorState,
    SensorSnapshot,
    SimulationTimestamp,
    ZoneSensorState,
    csv_headers,
    flatten_snapshot,
)


def snapshot(value: float = 21.5) -> SensorSnapshot:
    timestamp = SimulationTimestamp(
        1, 3, 2024, 2024, 1, 1, 1, 2, 1, 15, 0.25, 0.25, 1, 4, False
    )
    return SensorSnapshot(
        1,
        timestamp,
        OutdoorSensorState(5.0, 60.0),
        BuildingSensorState(1.0, 2.0, 3.0, {"fans": None}),
        (ZoneSensorState("Z", value, 0.0, None),),
    )


def test_snapshot_serializes_and_flattens_optional_nulls() -> None:
    item = snapshot()
    assert item.timestamp.identity() == (1, 1, 1, 15, 1)
    assert json.loads(item.to_json())["zones"][0]["zone_name"] == "Z"
    flat = flatten_snapshot(item, ("Z",), ("fans",))
    assert flat["meter.fans.raw_j"] is None
    assert flat["zone.Z.relative_humidity_percent"] is None
    assert csv_headers(("Z",), ("fans",)) == list(flat)


def test_snapshot_rejects_non_finite_required_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        snapshot(math.nan)

