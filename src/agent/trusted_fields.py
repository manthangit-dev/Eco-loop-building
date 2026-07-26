"""Deterministic authority for causal control-proposal metadata."""

from __future__ import annotations

from typing import Any

from src.agent.models import SupervisorRequest

TRUSTED_SYSTEM_FIELDS = frozenset(
    {
        "run_id",
        "environment_id",
        "source_state_sequence",
        "source_simulation_time_hours",
        "decision_sequence",
        "current_sequence",
        "valid_from_sequence",
        "expires_after_sequence",
        "component_type",
        "control_type",
        "actuator_key",
        "zone",
        "units",
        "schema_version",
        "dry_run_only",
    }
)
MODEL_SUGGESTED_FIELDS = frozenset({"requested_value", "strategy", "rationale", "objective"})
USER_REQUEST_FIELDS = frozenset({"objective_type", "zone", "proposal_value", "response_detail"})


def trusted_control_arguments(request: SupervisorRequest) -> dict[str, Any]:
    """Build replay-causal arguments; model-generated causal fields are never consulted."""
    if request.state_id is None or request.environment_id is None:
        raise ValueError("trusted state and environment are required")
    current = request.state_id + 1
    return {
        "run_id": request.run_id,
        "environment_id": request.environment_id,
        "source_state_sequence": request.state_id,
        "current_sequence": current,
        "decision_sequence": request.state_id,
        "valid_from_sequence": current,
        "expires_after_sequence": current + 1,
        "component_type": "Zone Temperature Control",
        "control_type": "Cooling Setpoint",
        "actuator_key": request.zone or "SPACE3-1",
        "zone": request.zone or "SPACE3-1",
        "units": request.proposal_units or "C",
        "requested_value": float(request.proposal_value or 0.0),
        "client_request_id": request.request_id,
        "rationale": "user/model value only; causal metadata is repository-owned",
    }
