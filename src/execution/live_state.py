"""Trusted committed live-state validation."""

from __future__ import annotations

import math

from src.execution.errors import ExecutionValidationError
from src.execution.models import TrustedLiveState


def validate_live_state(state: TrustedLiveState, environment: str, actuator: str) -> None:
    if not state.committed:
        raise ExecutionValidationError("live_state_not_committed")
    if state.warmup:
        raise ExecutionValidationError("warmup_state")
    if not state.api_ready:
        raise ExecutionValidationError("api_not_ready")
    if state.environment_id != environment:
        raise ExecutionValidationError("environment_mismatch")
    if state.callback_identity != "end_zone_timestep_after_zone_reporting":
        raise ExecutionValidationError("invalid_callback")
    if state.target_actuator_identity != actuator:
        raise ExecutionValidationError("actuator_scope_mismatch")
    if isinstance(state.current_zone_temperature, bool) or not math.isfinite(
        state.current_zone_temperature
    ):
        raise ExecutionValidationError("non_finite_live_state")
