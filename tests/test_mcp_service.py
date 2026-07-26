from pathlib import Path

import pytest
from src.mcp_server.config import load_mcp_settings
from src.mcp_server.models import ToolEnvelope, ToolRequest
from src.mcp_server.service import MCPToolService


@pytest.fixture(scope="module")
def service() -> MCPToolService:
    root = Path(__file__).resolve().parents[1]
    return MCPToolService(load_mcp_settings(root / "config/mcp_server.yaml"), audit=False)


def call(service: MCPToolService, name: str, arguments: dict[str, object]) -> ToolEnvelope:
    return service.call(
        ToolRequest(
            request_id=f"test-{name}-{len(str(arguments))}", tool_name=name, arguments=arguments
        )
    )


@pytest.mark.parametrize(
    "name",
    [
        "list_available_runs",
        "get_controller_status",
        "get_safety_guard_status",
        "list_available_actuators",
    ],
)
def test_repository_tools(service: MCPToolService, name: str) -> None:
    assert call(service, name, {"limit": 5}).success


def test_state_controller_safety_and_audit_tools(service: MCPToolService) -> None:
    run = {"run_id": "module8-live-control"}
    for name, arguments in (
        ("get_building_state", run),
        ("get_zone_state", {**run, "zone": "PLENUM-1"}),
        ("get_recent_state_history", {**run, "limit": 4}),
        ("get_controller_decisions", {**run, "limit": 2}),
        ("get_safety_decisions", {**run, "limit": 2}),
        ("get_physical_write_audit", {**run, "limit": 2}),
        ("get_run_energy_summary", run),
        ("get_comfort_evidence", run),
    ):
        assert call(service, name, dict(arguments)).success


def test_dry_run_guard_and_disabled_control(service: MCPToolService) -> None:
    base = {
        "run_id": "module8-live-control",
        "environment_id": "weather-1",
        "source_state_sequence": 10,
        "current_sequence": 11,
        "component_type": "Zone Temperature Control",
        "control_type": "Cooling Setpoint",
        "actuator_key": "SPACE3-1",
        "zone": "SPACE3-1",
        "units": "C",
        "requested_value": 24.0,
        "client_request_id": "client",
    }
    allowed = call(service, "validate_control_proposal", base)
    assert allowed.success and allowed.data["guard_outcome"] == "ALLOW"
    plenum = call(
        service,
        "validate_control_proposal",
        {**base, "zone": "PLENUM-1", "actuator_key": "PLENUM-1"},
    )
    assert plenum.success and plenum.data["reason_code"] == "plenum_zone_rejected"
    disabled = call(service, "propose_guarded_control", {"runtime_mode": "guarded_control"})
    assert not disabled.success


def test_unknown_tool_structured_error(service: MCPToolService) -> None:
    response = call(service, "unknown", {})
    assert not response.success and response.errors[0].code == "unknown_tool"
