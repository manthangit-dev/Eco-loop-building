"""Exact-window Module 14A approval creation and validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from src.execution.approval import CONFIRMATION
from src.execution.errors import ExecutionValidationError
from src.execution.models import ExecutionApproval, ExecutionMode
from src.planning.provenance import planning_fingerprint


def create_exact_approval(
    package: dict[str, Any],
    runtime: dict[str, Any],
    repository: str,
    expires_minutes: int = 30,
    maximum_writes: int = 20,
    maximum_resets: int = 2,
) -> ExecutionApproval:
    window = runtime["runtime_window"]
    selected = next(
        item for item in package["plans"] if item["plan_id"] == package["selected_plan_id"]
    )
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "repository_instance": repository,
        "simulation_only": True,
        "execution_mode": ExecutionMode.LIVE_SHORT_HORIZON,
        "selected_plan_id": package["selected_plan_id"],
        "plan_fingerprint": package["plan_fingerprint"],
        "planning_context_id": package["selected_context_id"],
        "rollout_id": package["selected_rollout_id"],
        "rollout_fingerprint": package["selected_rollout_fingerprint"],
        "ledger_evaluation_id": package["selected_ledger_evaluation_id"],
        "ledger_evaluation_fingerprint": package["selected_ledger_fingerprint"],
        "model_fingerprint": package["rollouts"][0]["model_id"],
        "actuator_identity": selected["actuator_identity"],
        "zone": selected["target_zone"],
        "units": "C",
        "allowed_action_count": len(selected["actions"]),
        "allowed_requested_values": tuple(x["requested_value"] for x in selected["actions"]),
        "maximum_write_count": maximum_writes,
        "maximum_reset_count": maximum_resets,
        "created_at": now,
        "expires_at": now + timedelta(minutes=expires_minutes),
        "permitted_environment": "weather-3",
        "expected_source_idf_checksum": runtime["parent_checksum"],
        "expected_baseline_idf_checksum": runtime["parent_checksum"],
        "expected_epw_checksum": runtime["epw_checksum"],
        "operator_confirmation_text": CONFIRMATION,
        "approval_schema_version": 2,
        "approved_weather_year_semantics": window["weather_year_semantics"],
        "approved_start_month": window["start_month"],
        "approved_start_day": window["start_day"],
        "approved_start_hour": window["start_hour"],
        "approved_start_minute": window["start_minute"],
        "approved_end_month": window["end_month"],
        "approved_end_day": window["end_day"],
        "approved_end_hour": window["end_hour"],
        "approved_end_minute": window["end_minute"],
        "approved_zone_timestep_minutes": window["zone_timestep_minutes"],
        "approved_planning_timestamp": window["planning_timestamp"],
        "approved_source_state_timestamp": window["source_state_timestamp"],
        "approved_forecast_start_timestamp": window["forecast_start_timestamp"],
        "approved_forecast_end_timestamp": window["forecast_end_timestamp"],
        "approved_runperiod_fingerprint": window["runperiod_fingerprint"],
        "approved_runtime_idf_fingerprint": runtime["derived_idf_fingerprint"],
        "approved_initial_condition_policy": {
            "temperature_c": 0.05,
            "outdoor_c": 0.05,
            "setpoint_c": 0.05,
            "occupancy_people": 0.01,
        },
    }
    approval_id = planning_fingerprint({**payload, "created_at": now.isoformat()})
    return ExecutionApproval(approval_id=approval_id, **payload)


def validate_exact_approval(
    approval: ExecutionApproval,
    package: dict[str, Any],
    runtime: dict[str, Any],
) -> None:
    if approval.approval_schema_version != 2:
        raise ExecutionValidationError("runtime_calendar_mismatch")
    if approval.selected_plan_id != package["selected_plan_id"]:
        raise ExecutionValidationError("plan_fingerprint_mismatch")
    exact = {
        "plan_fingerprint": package["plan_fingerprint"],
        "rollout_fingerprint": package["selected_rollout_fingerprint"],
        "ledger_evaluation_fingerprint": package["selected_ledger_fingerprint"],
        "approved_runtime_idf_fingerprint": runtime["derived_idf_fingerprint"],
        "approved_runperiod_fingerprint": runtime["runtime_window"]["runperiod_fingerprint"],
    }
    reasons = {
        "plan_fingerprint": "plan_fingerprint_mismatch",
        "rollout_fingerprint": "rollout_fingerprint_mismatch",
        "ledger_evaluation_fingerprint": "ledger_fingerprint_mismatch",
        "approved_runtime_idf_fingerprint": "runperiod_fingerprint_mismatch",
        "approved_runperiod_fingerprint": "runperiod_fingerprint_mismatch",
    }
    for field, expected in exact.items():
        if getattr(approval, field) != expected:
            raise ExecutionValidationError(reasons[field])
    window = runtime["runtime_window"]
    calendar = {
        "approved_start_month": "start_month",
        "approved_start_day": "start_day",
        "approved_start_hour": "start_hour",
        "approved_start_minute": "start_minute",
        "approved_end_month": "end_month",
        "approved_end_day": "end_day",
        "approved_end_hour": "end_hour",
        "approved_end_minute": "end_minute",
    }
    for approval_field, window_field in calendar.items():
        if getattr(approval, approval_field) != window[window_field]:
            raise ExecutionValidationError("runtime_calendar_mismatch")
    if approval.approved_planning_timestamp != window["planning_timestamp"]:
        raise ExecutionValidationError("planning_timestamp_mismatch")
    if approval.approved_source_state_timestamp != window["source_state_timestamp"]:
        raise ExecutionValidationError("source_state_window_mismatch")
    if (
        approval.approved_forecast_start_timestamp != window["forecast_start_timestamp"]
        or approval.approved_forecast_end_timestamp != window["forecast_end_timestamp"]
    ):
        raise ExecutionValidationError("forecast_window_mismatch")
    if approval.approved_zone_timestep_minutes != window["zone_timestep_minutes"]:
        raise ExecutionValidationError("zone_timestep_mismatch")
