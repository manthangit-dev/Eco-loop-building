"""Local operator approval creation and fail-closed validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from src.execution.config import ExecutionSettings
from src.execution.errors import ExecutionValidationError
from src.execution.models import ExecutionApproval, ExecutionMode
from src.planning.provenance import planning_fingerprint

CONFIRMATION = (
    "I approve simulation-only EnergyPlus actuation for the exact bound plan. "
    "This does not approve real-building or hardware control."
)


def create_approval(
    binding: dict[str, Any],
    settings: ExecutionSettings,
    mode: ExecutionMode,
    expires_in_minutes: int,
    maximum_writes: int,
    maximum_resets: int,
    simulation_only: bool,
    confirmed: bool,
) -> ExecutionApproval:
    if not simulation_only:
        raise ExecutionValidationError("simulation_only_required")
    if not confirmed:
        raise ExecutionValidationError("operator_confirmation_required")
    if expires_in_minutes <= 0 or expires_in_minutes > 1440:
        raise ExecutionValidationError("approval_expiry_invalid")
    if maximum_writes <= 0 or maximum_writes > settings.maximum_writes:
        raise ExecutionValidationError("write_limit_invalid")
    if maximum_resets <= 0 or maximum_resets > settings.maximum_resets:
        raise ExecutionValidationError("reset_limit_invalid")
    now = datetime.now(UTC)
    payload = {
        "repository_instance": str(settings.root.resolve()),
        "simulation_only": True,
        "execution_mode": mode,
        "selected_plan_id": binding["plan_id"],
        "plan_fingerprint": binding["plan_fingerprint"],
        "planning_context_id": binding["planning_context_id"],
        "rollout_id": binding["rollout_id"],
        "rollout_fingerprint": binding["rollout_fingerprint"],
        "ledger_evaluation_id": binding["ledger_evaluation_id"],
        "ledger_evaluation_fingerprint": binding["ledger_evaluation_fingerprint"],
        "model_fingerprint": binding["model_fingerprint"],
        "actuator_identity": binding["actuator_identity"],
        "zone": binding["target_zone"],
        "units": binding["units"],
        "allowed_action_count": binding["action_count"],
        "allowed_requested_values": tuple(x["requested_value"] for x in binding["actions"]),
        "maximum_write_count": maximum_writes,
        "maximum_reset_count": maximum_resets,
        "created_at": now,
        "expires_at": now + timedelta(minutes=expires_in_minutes),
        "permitted_environment": settings.permitted_environment,
        "expected_source_idf_checksum": binding["source_idf_checksum"],
        "expected_baseline_idf_checksum": binding["baseline_idf_checksum"],
        "expected_epw_checksum": binding["epw_checksum"],
        "operator_confirmation_text": CONFIRMATION,
        "approval_schema_version": settings.approval_schema_version,
    }
    approval_id = planning_fingerprint({**payload, "created_at": now.isoformat()})
    return ExecutionApproval(approval_id=approval_id, **payload)


def validate_approval(
    approval: ExecutionApproval | None,
    binding: dict[str, Any],
    settings: ExecutionSettings,
    mode: ExecutionMode,
    now: datetime | None = None,
) -> None:
    if approval is None:
        raise ExecutionValidationError("approval_missing")
    current = now or datetime.now(UTC)
    if approval.expires_at <= current:
        raise ExecutionValidationError("approval_expired")
    if not approval.simulation_only:
        raise ExecutionValidationError("simulation_only_required")
    if approval.consumed_session_id is not None:
        raise ExecutionValidationError("approval_already_consumed")
    exact = {
        "selected_plan_id": "plan_no_longer_eligible",
        "plan_fingerprint": "plan_fingerprint_mismatch",
        "rollout_fingerprint": "rollout_fingerprint_mismatch",
        "ledger_evaluation_fingerprint": "ledger_fingerprint_mismatch",
        "model_fingerprint": "model_fingerprint_mismatch",
        "zone": "actuator_scope_mismatch",
        "actuator_identity": "actuator_scope_mismatch",
        "units": "actuator_scope_mismatch",
        "expected_source_idf_checksum": "model_checksum_mismatch",
        "expected_baseline_idf_checksum": "model_checksum_mismatch",
        "expected_epw_checksum": "weather_checksum_mismatch",
    }
    source = {
        "selected_plan_id": binding["plan_id"],
        "plan_fingerprint": binding["plan_fingerprint"],
        "rollout_fingerprint": binding["rollout_fingerprint"],
        "ledger_evaluation_fingerprint": binding["ledger_evaluation_fingerprint"],
        "model_fingerprint": binding["model_fingerprint"],
        "zone": binding["target_zone"],
        "actuator_identity": binding["actuator_identity"],
        "units": binding["units"],
        "expected_source_idf_checksum": binding["source_idf_checksum"],
        "expected_baseline_idf_checksum": binding["baseline_idf_checksum"],
        "expected_epw_checksum": binding["epw_checksum"],
    }
    for field, reason in exact.items():
        if getattr(approval, field) != source[field]:
            raise ExecutionValidationError(reason)
    if approval.execution_mode != mode:
        raise ExecutionValidationError("wrong_execution_mode")
    if approval.allowed_action_count != binding["action_count"]:
        raise ExecutionValidationError("action_limit_invalid")
