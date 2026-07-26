"""Immutable Module 14 execution records."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field

from src.planning.provenance import planning_fingerprint


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExecutionMode(StrEnum):
    REPLAY_DRY_RUN = "REPLAY_DRY_RUN"
    LIVE_SHADOW = "LIVE_SHADOW"
    LIVE_SHORT_HORIZON = "LIVE_SHORT_HORIZON"
    FAULT_INJECTION_FAKE_WRITER = "FAULT_INJECTION_FAKE_WRITER"


class ExecutionState(StrEnum):
    IDLE = "IDLE"
    PREFLIGHT = "PREFLIGHT"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    ARMED = "ARMED"
    WAITING_FOR_LIVE_STATE = "WAITING_FOR_LIVE_STATE"
    EXECUTING = "EXECUTING"
    HOLDING = "HOLDING"
    FALLBACK_ACTIVE = "FALLBACK_ACTIVE"
    RESETTING_TO_NATIVE = "RESETTING_TO_NATIVE"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"


class ExecutionApproval(FrozenModel):
    approval_id: str
    repository_instance: str
    simulation_only: bool
    execution_mode: ExecutionMode
    selected_plan_id: str
    plan_fingerprint: str
    planning_context_id: str
    rollout_id: str
    rollout_fingerprint: str
    ledger_evaluation_id: str
    ledger_evaluation_fingerprint: str
    model_fingerprint: str
    actuator_identity: str
    zone: str
    units: str
    allowed_action_count: int = Field(gt=0)
    allowed_requested_values: tuple[float, ...]
    maximum_write_count: int = Field(gt=0)
    maximum_reset_count: int = Field(gt=0)
    created_at: datetime
    expires_at: datetime
    permitted_environment: str
    expected_source_idf_checksum: str
    expected_baseline_idf_checksum: str
    expected_epw_checksum: str
    operator_confirmation_text: str
    approval_schema_version: int = 1
    consumed_session_id: str | None = None
    approved_weather_year_semantics: str | None = None
    approved_start_month: int | None = None
    approved_start_day: int | None = None
    approved_start_hour: int | None = None
    approved_start_minute: int | None = None
    approved_end_month: int | None = None
    approved_end_day: int | None = None
    approved_end_hour: int | None = None
    approved_end_minute: int | None = None
    approved_zone_timestep_minutes: int | None = None
    approved_planning_timestamp: str | None = None
    approved_source_state_timestamp: str | None = None
    approved_forecast_start_timestamp: str | None = None
    approved_forecast_end_timestamp: str | None = None
    approved_runperiod_fingerprint: str | None = None
    approved_runtime_idf_fingerprint: str | None = None
    approved_initial_condition_policy: dict[str, float] | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def approval_fingerprint(self) -> str:
        return planning_fingerprint(self.model_dump(exclude={"approval_fingerprint"}, mode="json"))


class ScheduledAction(FrozenModel):
    plan_action_id: str
    action_sequence: int
    timestep_offset: int
    intended_simulation_timestamp: str
    earliest_timestep: int
    latest_timestep: int
    requested_value: float
    units: str
    action_type: str
    status: str = "PENDING"


class TrustedLiveState(FrozenModel):
    execution_session_id: str
    run_id: str
    environment_id: str
    current_state_id: int = Field(gt=0)
    current_simulation_timestamp: str
    simulation_time_hours: float = Field(strict=True)
    current_zone_temperature: float = Field(strict=True)
    current_effective_cooling_setpoint: float | None
    current_occupancy: float | None
    api_ready: bool
    warmup: bool
    callback_identity: str
    target_actuator_identity: str
    current_plan_action_index: int
    current_sequence: int = Field(gt=0)
    committed: bool = True


class StateTransition(FrozenModel):
    sequence: int
    from_state: ExecutionState
    to_state: ExecutionState
    reason_code: str


class ActionOutcome(FrozenModel):
    action: ScheduledAction
    guard_outcome: str
    guard_reason: str
    guarded_value: float | None
    writer_status: str
    terminal_status: str
    physical_write: bool


class ExecutionReport(FrozenModel):
    status: str
    session_id: str
    approval_id: str
    mode: ExecutionMode
    final_state: ExecutionState
    transitions: tuple[StateTransition, ...]
    actions: tuple[ActionOutcome, ...]
    scheduled_action_count: int
    executed_action_count: int
    skipped_action_count: int
    duplicate_action_count: int
    physical_set_calls: int
    physical_reset_calls: int
    fallback_activation_count: int
    mandatory_native_reset: bool
    unguarded_write_count: int
    runtime_seconds: float
