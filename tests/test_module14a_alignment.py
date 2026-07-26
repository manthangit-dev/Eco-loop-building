from __future__ import annotations

from copy import deepcopy

import pytest
from src.execution.alignment import (
    classify_effect,
    compare_initial_conditions,
    reconcile_aligned_points,
    validate_runtime_window,
)
from src.execution.errors import ExecutionValidationError


def window() -> dict[str, object]:
    return {
        "start_month": 7,
        "start_day": 19,
        "start_hour": 10,
        "start_minute": 45,
        "end_month": 7,
        "end_day": 19,
        "end_hour": 13,
        "end_minute": 45,
        "zone_timestep_minutes": 15,
        "planning_timestamp": "07-19 10:45",
        "source_state_timestamp": "2013-07-19 10:45",
        "forecast_start_timestamp": "07-19 11:00",
        "forecast_end_timestamp": "07-19 13:45",
        "runperiod_fingerprint": "exact",
    }


@pytest.mark.parametrize(
    "field,reason",
    [
        ("start_month", "runtime_calendar_mismatch"),
        ("start_day", "runtime_calendar_mismatch"),
        ("start_hour", "runtime_calendar_mismatch"),
        ("zone_timestep_minutes", "zone_timestep_mismatch"),
        ("runperiod_fingerprint", "runperiod_fingerprint_mismatch"),
        ("forecast_start_timestamp", "forecast_window_mismatch"),
        ("source_state_timestamp", "source_state_window_mismatch"),
    ],
)
def test_exact_window_rejects_mutation(field: str, reason: str) -> None:
    approved, actual = window(), deepcopy(window())
    actual[field] = "wrong"
    with pytest.raises(ExecutionValidationError, match=reason):
        validate_runtime_window(approved, actual)


def test_exact_window_accepts_match() -> None:
    validate_runtime_window(window(), window())


@pytest.mark.parametrize(
    "expected,setpoints,temperatures,energy",
    [
        ("NO_EFFECT", [0.01], [1.0], 100.0),
        ("CONTROL_PATH_ONLY", [1.5], [0.0001], 0.5),
        ("MEANINGFUL_EFFECT", [1.5], [0.01], 0.0),
        ("MEANINGFUL_EFFECT", [1.5], [0.0], 2.0),
    ],
)
def test_effect_classification(
    expected: str, setpoints: list[float], temperatures: list[float], energy: float
) -> None:
    assert classify_effect(setpoints, temperatures, energy, 0.05, 0.001, 1.0) == expected


def test_initial_condition_compatibility_and_rejection() -> None:
    base = {"temperature": 25.0, "outdoor": 30.0, "setpoint": 28.4, "occupancy": 11.0}
    assert compare_initial_conditions([base, dict(base)], 0.05, 0.05, 0.05)["status"] == "PASS"
    changed = dict(base, temperature=25.2)
    result = compare_initial_conditions([base, changed], 0.05, 0.05, 0.05)
    assert result["status"] == "FAIL" and result["failed_fields"] == ["temperature"]


def test_reconciliation_alignment_and_rejection() -> None:
    predicted = [
        {
            "timestamp": "07-19 11:00",
            "temperature_c": 25.0,
            "lower_c": 24.0,
            "upper_c": 26.0,
            "setpoint_c": 26.9,
        }
    ]
    actual = [{"timestamp": "07-19 11:00", "temperature_c": 25.5, "effective_setpoint_c": 26.9}]
    result = reconcile_aligned_points(predicted, actual, 1)
    assert result["aligned_point_count"] == 1 and result["mae_c"] == 0.5
    actual[0]["timestamp"] = "07-19 11:15"
    with pytest.raises(ExecutionValidationError, match="reconciliation_timestamp_mismatch"):
        reconcile_aligned_points(predicted, actual, 1)
