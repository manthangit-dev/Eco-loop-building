from dataclasses import replace
from pathlib import Path

import pytest
from src.energyplus.actuator_definitions import load_actuator_settings
from src.energyplus.actuator_plan import WindowPosition, build_plan

ROOT = Path(__file__).resolve().parents[1]


def test_plan_positions_and_bounded_target() -> None:
    plan = build_plan(load_actuator_settings(ROOT / "config/actuators.yaml", ROOT))
    assert plan.approved_setpoint == pytest.approx(24.9)
    assert plan.position(7, 19, 13, 45) is WindowPosition.BEFORE
    assert plan.position(7, 19, 14, 15) is WindowPosition.DURING
    assert plan.position(7, 19, 15, 30) is WindowPosition.AFTER


def test_plan_rejects_bad_window_and_offset() -> None:
    plan = build_plan(load_actuator_settings(ROOT / "config/actuators.yaml", ROOT))
    with pytest.raises(ValueError, match="after start"):
        replace(plan, end_minute_of_day=plan.start_minute_of_day)
    with pytest.raises(ValueError, match="offset"):
        replace(plan, offset=2.0)
    with pytest.raises(ValueError, match="15-minute"):
        replace(plan, start_minute_of_day=841)
