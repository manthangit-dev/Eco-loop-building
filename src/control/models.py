"""Immutable typed controller records."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any

from src.control.reason_codes import ActionType, ControllerMode, DecisionReason

SAFETY_GUARD_PENDING = "not_implemented_module_8_pending"


@dataclass(frozen=True)
class ActuatorIdentity:
    component_type: str
    control_type: str
    unique_key: str
    units: str

    @property
    def key(self) -> str:
        return "|".join((self.component_type, self.control_type, self.unique_key, self.units))


@dataclass(frozen=True)
class ControlDecision:
    decision_id: str
    run_id: str
    decision_sequence: int
    based_on_state_sequence: int
    based_on_state_fingerprint: str
    created_at_utc: str
    target_zone_id: str
    target_zone_name: str
    controller_mode_before: ControllerMode
    controller_mode_after: ControllerMode
    reason_code: DecisionReason
    explanation: str
    occupancy: float
    zone_temperature_celsius: float | None
    baseline_setpoint_celsius: float | None
    requested_setpoint_celsius: float | None
    approved_setpoint_celsius: float | None
    clamped: bool
    action_type: ActionType
    command_ttl: int
    intended_effective_sequence: int
    actuator: ActuatorIdentity
    shadow_mode: bool
    safety_guard_status: str = SAFETY_GUARD_PENDING
    validation_issues: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            self.based_on_state_sequence < 1
            or self.intended_effective_sequence <= self.based_on_state_sequence
        ):
            raise ValueError("Decision must causally precede its intended effect.")
        if self.safety_guard_status != SAFETY_GUARD_PENDING:
            raise ValueError("Module 8 safety guard must remain pending.")
        for value in (self.requested_setpoint_celsius, self.approved_setpoint_celsius):
            if value is not None and not math.isfinite(value):
                raise ValueError("Setpoint must be finite.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ControlCommand:
    command_id: str
    decision_id: str
    target_zone_id: str
    target_zone_name: str
    actuator: ActuatorIdentity
    setpoint_celsius: float | None
    issued_from_sequence: int
    valid_from_sequence: int
    expires_after_sequence: int
    reset_required: bool
    mode: ControllerMode
    reason: DecisionReason
    shadow_mode: bool
    fingerprint: str

    def __post_init__(self) -> None:
        if self.valid_from_sequence <= self.issued_from_sequence:
            raise ValueError("Command cannot act on its source state.")
        if self.expires_after_sequence < self.valid_from_sequence:
            raise ValueError("Command expiry precedes validity.")
        if not self.reset_required and (
            self.setpoint_celsius is None or not math.isfinite(self.setpoint_celsius)
        ):
            raise ValueError("Apply command requires a finite setpoint.")


@dataclass(frozen=True)
class ZoneControllerMemory:
    zone_id: str
    current_mode: ControllerMode = ControllerMode.NATIVE
    previous_mode: ControllerMode = ControllerMode.NATIVE
    last_evaluated_state_sequence: int = 0
    last_decision_sequence: int = 0
    last_command_sequence: int = 0
    last_command_setpoint: float | None = None
    last_native_setpoint: float | None = None
    consecutive_occupied_timesteps: int = 0
    consecutive_unoccupied_timesteps: int = 0
    hold_timesteps_remaining: int = 0
    hysteresis_active: bool = False
    recovery_active: bool = False
    active_command: bool = False
    command_expiry_sequence: int = 0
    last_reset_sequence: int = 0
    last_reason_code: DecisionReason = DecisionReason.NO_ACTION


@dataclass(frozen=True)
class ControllerSnapshot:
    run_id: str
    based_on_state_sequence: int
    memories: tuple[ZoneControllerMemory, ...]


@dataclass(frozen=True)
class CommandOutcome:
    outcome_id: str
    command_id: str
    observed_state_sequence: int
    event_type: str
    effective_setpoint_celsius: float | None
    zone_temperature_celsius: float | None
    occupancy: float
    outdoor_temperature_celsius: float
    facility_electricity_raw_j: float
    hvac_electricity_raw_j: float
    association_label: str = "post-command association"


@dataclass(frozen=True)
class ControllerRunMetadata:
    run_id: str
    simulation_run_id: str
    mode: str
    started_at_utc: str
    model_checksum: str
    weather_checksum: str
    expected_state_count: int


@dataclass(frozen=True)
class ControllerRunCompletion:
    run_id: str
    status: str
    finished_at_utc: str
    state_count: int
    decision_count: int
    command_count: int
    set_call_count: int
    reset_count: int
    expiry_count: int
    rejected_count: int
    api_error_count: int
    callback_error_count: int


def deterministic_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()
