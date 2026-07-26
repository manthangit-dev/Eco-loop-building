"""Pure deterministic per-zone fallback policy."""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.control.config import FallbackSettings
from src.control.models import ZoneControllerMemory
from src.control.reason_codes import ActionType, ControllerMode, DecisionReason
from src.state.models import ZoneState


@dataclass(frozen=True)
class PolicyResult:
    mode: ControllerMode
    reason: DecisionReason
    action: ActionType
    requested: float | None
    approved: float | None
    clamped: bool
    explanation: str
    memory: ZoneControllerMemory
    baseline: float | None = None


def evaluate_zone(
    zone: ZoneState,
    memory: ZoneControllerMemory,
    settings: FallbackSettings,
    sequence: int,
    *,
    enabled: bool = True,
) -> PolicyResult:
    occupied = zone.occupant_count > 0
    occupied_count = memory.consecutive_occupied_timesteps + 1 if occupied else 0
    unoccupied_count = memory.consecutive_unoccupied_timesteps + 1 if not occupied else 0
    base_memory = ZoneControllerMemory(
        **{
            **memory.__dict__,
            "consecutive_occupied_timesteps": occupied_count,
            "consecutive_unoccupied_timesteps": unoccupied_count,
            "last_evaluated_state_sequence": sequence,
            "hold_timesteps_remaining": max(0, memory.hold_timesteps_remaining - 1),
        }
    )
    if not enabled:
        return _result(
            base_memory,
            ControllerMode.DISABLED,
            DecisionReason.DISABLED,
            ActionType.RESET,
            None,
            "Controller disabled.",
        )
    if zone.is_plenum:
        return _result(
            base_memory,
            ControllerMode.NATIVE,
            DecisionReason.REJECT_PLENUM,
            ActionType.NO_ACTION,
            None,
            "Plenum control is prohibited.",
        )
    if zone.exact_name not in settings.approved_zones:
        return _result(
            base_memory,
            ControllerMode.NATIVE,
            DecisionReason.REJECT_UNAPPROVED_ZONE,
            ActionType.REJECT,
            None,
            "Zone is not approved.",
        )
    if not math.isfinite(zone.mean_air_temperature_c):
        return _result(
            base_memory,
            ControllerMode.FAILSAFE_RESET,
            DecisionReason.REJECT_MISSING_DATA,
            ActionType.RESET,
            None,
            "Zone temperature unavailable.",
        )
    observed_baseline = zone.effective_cooling_setpoint_c
    if observed_baseline is None or not math.isfinite(observed_baseline):
        return _result(
            base_memory,
            ControllerMode.FAILSAFE_RESET,
            DecisionReason.REJECT_MISSING_DATA,
            ActionType.RESET,
            None,
            "Verified effective cooling setpoint unavailable.",
        )
    baseline = (
        memory.last_native_setpoint
        if memory.active_command and memory.last_native_setpoint is not None
        else observed_baseline
    )
    if memory.hold_timesteps_remaining > 0 and memory.active_command:
        return _result(
            base_memory,
            ControllerMode.HOLD,
            DecisionReason.HOLD_CURRENT_COMMAND,
            ActionType.APPLY_SETPOINT,
            memory.last_command_setpoint,
            "Minimum hold remains active.",
            baseline,
        )
    if occupied:
        recovery = zone.mean_air_temperature_c > settings.hot_threshold or (
            memory.recovery_active
            and zone.mean_air_temperature_c > settings.hot_threshold - settings.hysteresis
        )
        requested = min(baseline, settings.recovery_setpoint) if recovery else baseline
        mode = ControllerMode.OCCUPIED_RECOVERY if recovery else ControllerMode.OCCUPIED_NORMAL
        reason = (
            DecisionReason.APPLY_OCCUPIED_RECOVERY
            if recovery
            else DecisionReason.APPLY_OCCUPIED_NORMAL
        )
        explanation = (
            "Occupied hot-zone recovery." if recovery else "Occupied native setpoint maintained."
        )
    elif unoccupied_count <= settings.occupancy_grace:
        requested = baseline
        mode = ControllerMode.VACANCY_GRACE
        reason = DecisionReason.VACANCY_GRACE
        explanation = "Recent vacancy remains in occupied grace period."
    elif zone.mean_air_temperature_c >= settings.protection_threshold:
        requested = baseline
        mode = ControllerMode.OCCUPIED_NORMAL
        reason = DecisionReason.TEMPERATURE_PROTECTION
        explanation = "Relaxation prevented by temperature protection."
    else:
        requested = min(baseline + settings.relaxed_offset, settings.maximum_relaxed)
        mode = ControllerMode.UNOCCUPIED_RELAXED
        reason = DecisionReason.APPLY_UNOCCUPIED_RELAXATION
        explanation = "Unoccupied zone receives bounded relaxation."
    lower = max(settings.minimum_setpoint, baseline - settings.maximum_delta)
    upper = min(settings.maximum_setpoint, baseline + settings.maximum_delta)
    approved = min(max(requested, lower), upper)
    clamped = approved != requested
    updated = ZoneControllerMemory(
        **{
            **base_memory.__dict__,
            "previous_mode": memory.current_mode,
            "current_mode": mode,
            "last_native_setpoint": baseline,
            "last_command_setpoint": approved,
            "last_command_sequence": sequence,
            "hold_timesteps_remaining": settings.minimum_hold,
            "hysteresis_active": recovery if occupied else False,
            "recovery_active": recovery if occupied else False,
            "active_command": True,
            "command_expiry_sequence": sequence + settings.command_ttl,
            "last_reason_code": reason,
        }
    )
    return PolicyResult(
        mode,
        reason,
        ActionType.APPLY_SETPOINT,
        requested,
        approved,
        clamped,
        explanation,
        updated,
        baseline,
    )


def _result(
    memory: ZoneControllerMemory,
    mode: ControllerMode,
    reason: DecisionReason,
    action: ActionType,
    value: float | None,
    explanation: str,
    baseline: float | None = None,
) -> PolicyResult:
    updated = ZoneControllerMemory(
        **{
            **memory.__dict__,
            "previous_mode": memory.current_mode,
            "current_mode": mode,
            "last_reason_code": reason,
            "active_command": action is ActionType.APPLY_SETPOINT,
        }
    )
    return PolicyResult(mode, reason, action, value, value, False, explanation, updated, baseline)
