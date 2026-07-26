"""Module 14A calendar binding, context selection, and effect validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.execution.errors import ExecutionValidationError
from src.planning.provenance import planning_fingerprint


@dataclass(frozen=True)
class AlignmentSettings:
    root: Path
    raw: dict[str, Any]

    @property
    def runtime_idf(self) -> Path:
        return self.root / str(self.raw["runtime_idf"])

    @property
    def parent_idf(self) -> Path:
        return self.root / str(self.raw["parent_idf"])


def load_alignment_settings(path: Path) -> AlignmentSettings:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))["module14a"]
    if raw["schema_version"] != 1 or raw["approval_schema_version"] != 2:
        raise ExecutionValidationError("unsupported_alignment_schema")
    if raw["zone_timestep_minutes"] != 15 or raw["horizon_timesteps"] != 12:
        raise ExecutionValidationError("zone_timestep_mismatch")
    return AlignmentSettings(path.resolve().parents[1], raw)


def runtime_window(settings: AlignmentSettings) -> dict[str, Any]:
    raw = settings.raw
    payload = {
        "weather_year_semantics": "TMY3_CALENDAR_2013",
        "start_month": raw["planning_month"],
        "start_day": raw["planning_day"],
        "start_hour": raw["planning_hour"],
        "start_minute": raw["planning_minute"],
        "end_month": raw["planning_month"],
        "end_day": raw["planning_day"],
        "end_hour": 13,
        "end_minute": 45,
        "zone_timestep_minutes": raw["zone_timestep_minutes"],
        "planning_timestamp": "07-19 10:45",
        "source_state_timestamp": "2013-07-19 10:45",
        "forecast_start_timestamp": raw["forecast_start"],
        "forecast_end_timestamp": raw["forecast_end"],
        "runperiod": "07-19/07-19 Friday",
    }
    payload["runperiod_fingerprint"] = planning_fingerprint(payload)
    return payload


def validate_runtime_window(approved: dict[str, Any], actual: dict[str, Any]) -> None:
    reasons = {
        "runperiod_fingerprint": "runperiod_fingerprint_mismatch",
        "planning_timestamp": "planning_timestamp_mismatch",
        "source_state_timestamp": "source_state_window_mismatch",
        "forecast_start_timestamp": "forecast_window_mismatch",
        "forecast_end_timestamp": "forecast_window_mismatch",
        "zone_timestep_minutes": "zone_timestep_mismatch",
    }
    for field, reason in reasons.items():
        if approved.get(field) != actual.get(field):
            raise ExecutionValidationError(reason)
    for field in (
        "start_month",
        "start_day",
        "start_hour",
        "start_minute",
        "end_month",
        "end_day",
        "end_hour",
        "end_minute",
    ):
        if approved.get(field) != actual.get(field):
            raise ExecutionValidationError("runtime_calendar_mismatch")


def classify_effect(
    setpoint_differences: list[float],
    temperature_differences: list[float],
    energy_difference: float,
    setpoint_tolerance: float,
    temperature_tolerance: float,
    energy_tolerance: float,
) -> str:
    if not any(abs(value) > setpoint_tolerance for value in setpoint_differences):
        return "NO_EFFECT"
    response = any(abs(value) > temperature_tolerance for value in temperature_differences)
    response = response or abs(energy_difference) > energy_tolerance
    return "MEANINGFUL_EFFECT" if response else "CONTROL_PATH_ONLY"


def compare_initial_conditions(
    states: list[dict[str, Any]],
    temperature_tolerance: float,
    outdoor_tolerance: float,
    setpoint_tolerance: float,
    occupancy_tolerance: float = 0.01,
) -> dict[str, Any]:
    if len(states) < 2:
        raise ExecutionValidationError("initial_condition_run_missing")
    fields = {
        "temperature": temperature_tolerance,
        "outdoor": outdoor_tolerance,
        "setpoint": setpoint_tolerance,
        "occupancy": occupancy_tolerance,
    }
    reference = states[0]
    differences = {
        field: max(abs(float(item[field]) - float(reference[field])) for item in states[1:])
        for field in fields
    }
    failures = [field for field, tolerance in fields.items() if differences[field] > tolerance]
    return {
        "status": "PASS" if not failures else "FAIL",
        "maximum_differences": differences,
        "failed_fields": failures,
        "fingerprint": planning_fingerprint({"states": states, "differences": differences}),
    }


def reconcile_aligned_points(
    predicted: list[dict[str, Any]],
    simulated: list[dict[str, Any]],
    timestamp_tolerance_seconds: float,
) -> dict[str, Any]:
    if len(predicted) != len(simulated):
        raise ExecutionValidationError("reconciliation_horizon_mismatch")
    points: list[dict[str, Any]] = []
    for sequence, (forecast, actual) in enumerate(zip(predicted, simulated, strict=True), 1):
        if forecast["timestamp"] != actual["timestamp"]:
            raise ExecutionValidationError("reconciliation_timestamp_mismatch")
        difference = float(actual["temperature_c"]) - float(forecast["temperature_c"])
        lower, upper = float(forecast["lower_c"]), float(forecast["upper_c"])
        points.append(
            {
                "sequence": sequence,
                "planning_timestamp": forecast["timestamp"],
                "runtime_timestamp": actual["timestamp"],
                "timestamp_difference_seconds": 0.0,
                "predicted_temperature_c": forecast["temperature_c"],
                "simulated_temperature_c": actual["temperature_c"],
                "prediction_error_c": difference,
                "empirical_lower_c": lower,
                "empirical_upper_c": upper,
                "interval_covered": lower <= float(actual["temperature_c"]) <= upper,
                "predicted_setpoint_c": forecast["setpoint_c"],
                "effective_setpoint_c": actual["effective_setpoint_c"],
            }
        )
    errors = [float(x["prediction_error_c"]) for x in points]
    count = len(errors)
    mae = sum(abs(x) for x in errors) / count
    return {
        "status": "PASS",
        "aligned_point_count": count,
        "excluded_point_count": 0,
        "timestamp_tolerance_seconds": timestamp_tolerance_seconds,
        "points": points,
        "mae_c": mae,
        "rmse_c": (sum(x * x for x in errors) / count) ** 0.5,
        "bias_c": sum(errors) / count,
        "maximum_error_c": max(abs(x) for x in errors),
        "interval_coverage": sum(bool(x["interval_covered"]) for x in points) / count,
    }
