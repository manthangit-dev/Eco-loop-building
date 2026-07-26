from dataclasses import replace

from src.control.fallback_policy import evaluate_zone
from src.control.models import ZoneControllerMemory
from src.control.reason_codes import ControllerMode, DecisionReason
from src.state.models import ZoneState

from tests.control_helpers import control_state, settings


def _zone(
    *,
    occupancy: float = 1.0,
    temperature: float = 24.0,
    setpoint: float | None = 23.9,
) -> ZoneState:
    return next(
        z
        for z in control_state(
            occupancy=occupancy, temperature=temperature, setpoint=setpoint
        ).zones
        if z.exact_name == "SPACE3-1"
    )


def test_occupied_normal_recovery_and_hysteresis() -> None:
    cfg = settings()
    normal = evaluate_zone(_zone(), ZoneControllerMemory("space3_1"), cfg, 1)
    assert normal.reason is DecisionReason.APPLY_OCCUPIED_NORMAL
    hot = evaluate_zone(_zone(temperature=26.0), normal.memory, cfg, 2)
    assert hot.mode is ControllerMode.HOLD
    hot = evaluate_zone(
        _zone(temperature=26.0), replace(normal.memory, hold_timesteps_remaining=0), cfg, 2
    )
    assert hot.reason is DecisionReason.APPLY_OCCUPIED_RECOVERY
    hysteresis = evaluate_zone(
        _zone(temperature=24.7), replace(hot.memory, hold_timesteps_remaining=0), cfg, 3
    )
    assert hysteresis.reason is DecisionReason.APPLY_OCCUPIED_RECOVERY


def test_vacancy_grace_relaxation_reoccupancy_and_protection() -> None:
    cfg = settings()
    memory = ZoneControllerMemory("space3_1")
    for sequence in range(1, 5):
        result = evaluate_zone(
            _zone(occupancy=0), replace(memory, hold_timesteps_remaining=0), cfg, sequence
        )
        memory = result.memory
    assert result.reason is DecisionReason.VACANCY_GRACE
    relaxed = evaluate_zone(_zone(occupancy=0), replace(memory, hold_timesteps_remaining=0), cfg, 5)
    assert relaxed.reason is DecisionReason.APPLY_UNOCCUPIED_RELAXATION
    protected = evaluate_zone(
        _zone(occupancy=0, temperature=28),
        replace(memory, consecutive_unoccupied_timesteps=4, hold_timesteps_remaining=0),
        cfg,
        5,
    )
    assert protected.reason is DecisionReason.TEMPERATURE_PROTECTION
    occupied = evaluate_zone(
        _zone(occupancy=1), replace(relaxed.memory, hold_timesteps_remaining=0), cfg, 6
    )
    assert occupied.reason is DecisionReason.APPLY_OCCUPIED_NORMAL


def test_missing_baseline_plenum_and_disabled_fail_closed() -> None:
    cfg = settings()
    memory = ZoneControllerMemory("space3_1")
    assert (
        evaluate_zone(_zone(setpoint=None), memory, cfg, 1).reason
        is DecisionReason.REJECT_MISSING_DATA
    )
    plenum = control_state().zones[0]
    assert (
        evaluate_zone(plenum, ZoneControllerMemory(plenum.zone_id), cfg, 1).reason
        is DecisionReason.REJECT_PLENUM
    )
    assert evaluate_zone(_zone(), memory, cfg, 1, enabled=False).reason is DecisionReason.DISABLED
