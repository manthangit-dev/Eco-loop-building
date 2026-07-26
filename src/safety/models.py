"""Immutable safety-boundary records."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from src.control.models import ActuatorIdentity, ControlCommand

SAFETY_SCHEMA_VERSION = 1


class GuardOutcome(StrEnum):
    ALLOW = "ALLOW"
    CLAMP = "CLAMP"
    HOLD_LAST_SAFE = "HOLD_LAST_SAFE"
    RESET_TO_NATIVE = "RESET_TO_NATIVE"
    REJECT_NO_WRITE = "REJECT_NO_WRITE"


class SafetyReason(StrEnum):
    ALLOWED = "allowed"
    ALLOWED_NATIVE_RESET = "allowed_native_reset"
    CLAMPED_ABSOLUTE_BOUND = "clamped_absolute_bound"
    CLAMPED_RATE_LIMIT = "clamped_rate_limit"
    HELD_LAST_SAFE = "held_last_safe"
    RAW_COMMAND_BYPASS_BLOCKED = "raw_command_bypass_blocked"
    UNAPPROVED_COMPONENT_TYPE = "unapproved_component_type"
    UNAPPROVED_CONTROL_TYPE = "unapproved_control_type"
    UNAPPROVED_ACTUATOR_KEY = "unapproved_actuator_key"
    UNAPPROVED_ZONE = "unapproved_zone"
    PLENUM_ZONE_REJECTED = "plenum_zone_rejected"
    ACTUATOR_IDENTITY_MISMATCH = "actuator_identity_mismatch"
    UNIT_MISMATCH = "unit_mismatch"
    MISSING_VALUE = "missing_value"
    NON_NUMERIC_VALUE = "non_numeric_value"
    NAN_VALUE = "nan_value"
    POSITIVE_INFINITY = "positive_infinity"
    NEGATIVE_INFINITY = "negative_infinity"
    OUT_OF_ABSOLUTE_BOUNDS = "out_of_absolute_bounds"
    EXCESSIVE_STEP_CHANGE = "excessive_step_change"
    IMPOSSIBLE_VALUE_ORDERING = "impossible_value_ordering"
    MISSING_STATE = "missing_state"
    STALE_STATE = "stale_state"
    FUTURE_STATE = "future_state"
    INVALID_TIMESTAMP = "invalid_timestamp"
    NON_MONOTONIC_STATE = "non_monotonic_state"
    WRONG_RUN_ID = "wrong_run_id"
    WRONG_ENVIRONMENT = "wrong_environment"
    WARMUP_STATE_REJECTED = "warmup_state_rejected"
    SIMULATION_NOT_READY = "simulation_not_ready"
    TERMINAL_STATE_WITHOUT_OUTCOME = "terminal_state_without_outcome"
    MISSING_COMMAND_ID = "missing_command_id"
    DUPLICATE_COMMAND_ID = "duplicate_command_id"
    CONFLICTING_DUPLICATE = "conflicting_duplicate"
    EXPIRED_COMMAND = "expired_command"
    COMMAND_FROM_FUTURE = "command_from_future"
    INVALID_COMMAND_SCHEMA = "invalid_command_schema"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    DISABLED_CONTROL = "disabled_control"
    SHUTDOWN_IN_PROGRESS = "shutdown_in_progress"
    NO_LAST_SAFE_COMMAND = "no_last_safe_command"
    LAST_SAFE_COMMAND_EXPIRED = "last_safe_command_expired"
    NATIVE_RESET_REQUIRED = "native_reset_required"
    GUARD_INTERNAL_ERROR = "guard_internal_error"
    PERSISTENCE_FAILURE_FAIL_CLOSED = "persistence_failure_fail_closed"


@dataclass(frozen=True)
class ProposedCommand:
    command_id: str
    decision_id: str
    run_id: str
    environment_id: str
    zone: str
    actuator: ActuatorIdentity
    requested_value: object
    source_state_sequence: int
    decision_sequence: int
    valid_from_sequence: int
    expires_after_sequence: int
    current_sequence: int
    source_simulation_time_hours: float
    decision_simulation_time_hours: float
    callback_simulation_time_hours: float
    environment_type: int = 3
    warmup: bool = False
    api_ready: bool = True
    reset_required: bool = False
    schema_version: int = SAFETY_SCHEMA_VERSION
    reapplication_of_guard_decision_id: str | None = None

    @classmethod
    def from_control_command(
        cls,
        command: ControlCommand,
        run_id: str,
        environment_id: str,
        current_sequence: int,
        simulation_time_hours: float,
    ) -> ProposedCommand:
        return cls(
            command.command_id,
            command.decision_id,
            run_id,
            environment_id,
            command.target_zone_name,
            command.actuator,
            command.setpoint_celsius,
            command.issued_from_sequence,
            command.issued_from_sequence,
            command.valid_from_sequence,
            command.expires_after_sequence,
            current_sequence,
            simulation_time_hours - 0.25,
            simulation_time_hours - 0.25,
            simulation_time_hours,
            reset_required=command.reset_required,
        )

    @property
    def fingerprint(self) -> str:
        return canonical_hash(asdict(self))


@dataclass(frozen=True)
class GuardDecision:
    guard_decision_id: str
    command_id: str
    run_id: str
    environment_id: str
    outcome: GuardOutcome
    reason: SafetyReason
    requested_value: object
    applied_value: float | None
    previous_safe_value: float | None
    source_state_sequence: int
    current_sequence: int
    safety_schema_version: int
    violations: tuple[SafetyReason, ...] = ()
    duplicate: bool = False

    @property
    def fingerprint(self) -> str:
        return canonical_hash(asdict(self))


_GUARD_TOKEN = object()


@dataclass(frozen=True, init=False)
class GuardedCommand:
    guard_decision_id: str
    command_id: str
    run_id: str
    environment_id: str
    zone: str
    actuator: ActuatorIdentity
    requested_value: float | None
    applied_value: float | None
    source_state_sequence: int
    decision_sequence: int
    valid_from_sequence: int
    expires_after_sequence: int
    outcome: GuardOutcome
    reason: SafetyReason
    safety_schema_version: int
    reset_required: bool
    authority_fingerprint: str

    def __init__(self, *, _token: object, authority_fingerprint: str, **values: Any) -> None:
        if _token is not _GUARD_TOKEN:
            raise TypeError("GuardedCommand can only be created by SafetyGuard.")
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "authority_fingerprint", authority_fingerprint)


def make_guarded_command(proposal: ProposedCommand, decision: GuardDecision) -> GuardedCommand:
    if decision.outcome not in {
        GuardOutcome.ALLOW,
        GuardOutcome.CLAMP,
        GuardOutcome.HOLD_LAST_SAFE,
        GuardOutcome.RESET_TO_NATIVE,
    }:
        raise ValueError("Reject decisions cannot create guarded commands.")
    requested = proposal.requested_value
    requested_float = (
        float(requested)
        if isinstance(requested, (int, float)) and not isinstance(requested, bool)
        else None
    )
    payload: dict[str, Any] = {
        "guard_decision_id": decision.guard_decision_id,
        "command_id": proposal.command_id,
        "run_id": proposal.run_id,
        "environment_id": proposal.environment_id,
        "zone": proposal.zone,
        "actuator": proposal.actuator,
        "requested_value": requested_float,
        "applied_value": decision.applied_value,
        "source_state_sequence": proposal.source_state_sequence,
        "decision_sequence": proposal.decision_sequence,
        "valid_from_sequence": proposal.valid_from_sequence,
        "expires_after_sequence": proposal.expires_after_sequence,
        "outcome": decision.outcome,
        "reason": decision.reason,
        "safety_schema_version": decision.safety_schema_version,
        "reset_required": decision.outcome == GuardOutcome.RESET_TO_NATIVE,
    }
    authority = canonical_hash({**payload, "actuator": asdict(proposal.actuator)})
    return GuardedCommand(_token=_GUARD_TOKEN, authority_fingerprint=authority, **payload)


def validate_guarded_authority(command: GuardedCommand) -> bool:
    payload = {k: v for k, v in asdict(command).items() if k != "authority_fingerprint"}
    return command.authority_fingerprint == canonical_hash(payload)


def canonical_hash(payload: object) -> str:
    raw = json.dumps(
        _json_safe(payload),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _json_safe(value: object) -> object:
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return "NaN"
        return "+Infinity" if value > 0 else "-Infinity"
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def numeric_reason(value: object) -> SafetyReason | None:
    if value is None:
        return SafetyReason.MISSING_VALUE
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return SafetyReason.NON_NUMERIC_VALUE
    number = float(value)
    if math.isnan(number):
        return SafetyReason.NAN_VALUE
    if number == math.inf:
        return SafetyReason.POSITIVE_INFINITY
    if number == -math.inf:
        return SafetyReason.NEGATIVE_INFINITY
    return None
