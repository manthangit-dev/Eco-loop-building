import pytest
from pydantic import ValidationError
from src.agent.policy import ToolPolicy
from src.agent.tool_parser import parse_tool_call
from src.llm.models import ModelToolCall, ProviderOutput
from src.mcp_server.registry import build_registry


def test_policy_allows_read_and_proposal_but_denies_control_and_overrides() -> None:
    policy = ToolPolicy(build_registry(False))
    policy.validate("get_building_state", {"run_id": "x"})
    policy.validate("validate_control_proposal", {})
    with pytest.raises(PermissionError):
        policy.validate("propose_guarded_control", {})
    with pytest.raises(PermissionError):
        policy.validate("get_building_state", {"approved": True})


def test_native_and_json_tool_call_parsing() -> None:
    native = ModelToolCall(name="get_run_metadata", arguments={"run_id": "x"})
    assert parse_tool_call(ProviderOutput(tool_call=native)) == native
    fallback = ProviderOutput(
        text='{"tool_call":{"name":"get_run_metadata","arguments":{"run_id":"x"}}}'
    )
    assert parse_tool_call(fallback) == native


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_nonfinite_tool_argument_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="non-finite"):
        parse_tool_call(ProviderOutput(tool_call=ModelToolCall(name="x", arguments={"v": value})))


def test_supervisor_schema_rejects_physical_mode() -> None:
    from src.agent.models import ObjectiveType, SupervisorRequest

    with pytest.raises(ValidationError):
        SupervisorRequest(
            request_id="x",
            objective_type=ObjectiveType.DESCRIBE_CURRENT_STATE,
            objective_text="x",
            run_id="run",
            dry_run_only=False,
        )
