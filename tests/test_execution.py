from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from scripts.planning_common import build
from src.agent.execution_policy import ExecutionClaimError, validate_execution_response
from src.execution.approval import create_approval, validate_approval
from src.execution.config import ExecutionSettings, load_execution_settings
from src.execution.errors import ExecutionValidationError, InvalidTransitionError
from src.execution.models import ExecutionMode, ExecutionState, TrustedLiveState
from src.execution.preflight import resolve_execution_binding
from src.execution.scheduler import ActionScheduler
from src.execution.state_machine import ExecutionStateMachine
from src.mcp_server.config import load_mcp_settings
from src.mcp_server.models import ToolRequest
from src.mcp_server.service import MCPToolService

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def settings() -> ExecutionSettings:
    return load_execution_settings(ROOT / "config/execution_orchestrator.yaml")


@pytest.fixture(scope="module")
def binding(settings: ExecutionSettings) -> dict[str, object]:
    return resolve_execution_binding(settings)


def test_config_is_fail_closed(settings: ExecutionSettings) -> None:
    assert settings.default_mode == ExecutionMode.REPLAY_DRY_RUN
    assert not settings.live_mode_enabled_by_default and settings.simulation_only
    with pytest.raises(ValidationError):
        ExecutionSettings.model_validate({**settings.model_dump(), "public_listener_allowed": True})


def test_preflight_binding(binding: dict[str, object]) -> None:
    assert binding["selected_plan_eligibility"] is True
    assert binding["first_action_module8_dry_run"] == "ALLOW"
    assert binding["target_zone"] == "SPACE3-1"


def test_approval_creation_validation_and_expiry(
    settings: ExecutionSettings, binding: dict[str, object]
) -> None:
    approval = create_approval(
        binding, settings, ExecutionMode.REPLAY_DRY_RUN, 30, 20, 2, True, True
    )
    validate_approval(approval, binding, settings, ExecutionMode.REPLAY_DRY_RUN)
    with pytest.raises(ExecutionValidationError, match="approval_expired"):
        validate_approval(
            approval,
            binding,
            settings,
            approval.execution_mode,
            now=approval.expires_at + timedelta(seconds=1),
        )
    with pytest.raises(ExecutionValidationError, match="wrong_execution_mode"):
        validate_approval(approval, binding, settings, ExecutionMode.LIVE_SHADOW)
    with pytest.raises(ExecutionValidationError, match="simulation_only_required"):
        create_approval(binding, settings, ExecutionMode.REPLAY_DRY_RUN, 30, 20, 2, False, True)


def test_state_machine_valid_and_invalid() -> None:
    machine = ExecutionStateMachine()
    with pytest.raises(InvalidTransitionError, match="invalid_state_transition"):
        machine.transition(ExecutionState.EXECUTING, "bypass")
    for state in (
        ExecutionState.PREFLIGHT,
        ExecutionState.APPROVAL_REQUIRED,
        ExecutionState.ARMED,
        ExecutionState.WAITING_FOR_LIVE_STATE,
        ExecutionState.EXECUTING,
        ExecutionState.RESETTING_TO_NATIVE,
        ExecutionState.COMPLETED,
    ):
        machine.transition(state, "test")
    with pytest.raises(InvalidTransitionError):
        machine.transition(ExecutionState.EXECUTING, "terminal")


def test_scheduler_exactly_once() -> None:
    _, plans = build()
    plan = next(x for x in plans if x.plan_id.startswith("3ae11"))
    scheduler = ActionScheduler(plan, 1, 1)
    assert scheduler.due(0) is None
    action = scheduler.due(1)
    assert action is not None and action.requested_value == 28.5
    scheduler.complete(action)
    assert scheduler.due(1) is None
    with pytest.raises(ExecutionValidationError, match="duplicate_action"):
        scheduler.complete(action)


def test_live_state_rejects_boolean_temperature() -> None:
    with pytest.raises(ValidationError):
        TrustedLiveState(
            execution_session_id="x",
            run_id="x",
            environment_id="weather-3",
            current_state_id=1,
            current_simulation_timestamp="x",
            simulation_time_hours=1.0,
            current_zone_temperature=True,
            current_effective_cooling_setpoint=None,
            current_occupancy=None,
            api_ready=True,
            warmup=False,
            callback_identity="x",
            target_actuator_identity="x",
            current_plan_action_index=0,
            current_sequence=1,
        )


@pytest.mark.parametrize(
    "tool",
    (
        "get_execution_approval_status",
        "get_plan_execution_status",
        "get_plan_execution_audit",
        "compare_execution_runs",
    ),
)
def test_execution_observability_tools_are_read_only(tool: str) -> None:
    service = MCPToolService(load_mcp_settings(ROOT / "config/mcp_server.yaml"), audit=False)
    response = service.call(ToolRequest(request_id=f"execution-{tool}", tool_name=tool))
    assert response.success
    assert service.definitions[tool].classification.value == "READ_ONLY"


@pytest.mark.parametrize(
    ("claim", "reason"),
    (
        ("real building", "false_real_building_claim"),
        ("annual savings", "false_annual_savings_claim"),
        ("guaranteed comfort", "false_guaranteed_comfort_claim"),
        ("I executed", "false_llm_execution_claim"),
    ),
)
def test_execution_claims_are_blocked(claim: str, reason: str) -> None:
    with pytest.raises(ExecutionClaimError, match=reason):
        validate_execution_response(claim)
