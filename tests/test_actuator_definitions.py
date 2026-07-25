from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from src.energyplus.actuator_definitions import load_actuator_settings

ROOT = Path(__file__).resolve().parents[1]


def test_valid_tracked_actuator_is_isolated_zone_cooling() -> None:
    settings = load_actuator_settings(ROOT / "config/actuators.yaml", ROOT)
    item = settings.definition
    assert item.component_type == "Zone Temperature Control"
    assert item.control_type == "Cooling Setpoint"
    assert item.target_zone == item.unique_key == "SPACE3-1"
    assert item.zone_specific and not item.shared_resource


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("component_type", "", "required"),
        ("control_type", "", "required"),
        ("unique_key", "", "required"),
        ("target_zone", "PLENUM-1", "plenum"),
        ("shared_resource", True, "isolated"),
        ("units", "W", "Celsius"),
        ("minimum", 27.0, "bounds"),
    ],
)
def test_invalid_actuator_is_rejected(field: str, value: Any, message: str) -> None:
    item = load_actuator_settings(ROOT / "config/actuators.yaml", ROOT).definition
    with pytest.raises(ValueError, match=message):
        replace(item, **{field: value})
