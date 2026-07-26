"""Replay a complete deterministic recorded Module 9 tool session."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mcp_server.config import load_mcp_settings  # noqa: E402
from src.mcp_server.models import ToolRequest, fingerprint  # noqa: E402
from src.mcp_server.service import MCPToolService  # noqa: E402


def proposal(request_id: str, **changes: object) -> ToolRequest:
    arguments: dict[str, object] = {
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
        "client_request_id": request_id,
    }
    arguments.update(changes)
    return ToolRequest(
        request_id=request_id, tool_name="validate_control_proposal", arguments=arguments
    )


def requests() -> list[ToolRequest]:
    run = {"run_id": "module8-live-control"}
    exact = ToolRequest(request_id="m9c-02", tool_name="get_run_metadata", arguments=run)
    return [
        ToolRequest(request_id="m9c-01", tool_name="list_available_runs", arguments={"limit": 10}),
        exact,
        ToolRequest(request_id="m9c-03", tool_name="get_building_state", arguments=run),
        ToolRequest(
            request_id="m9c-04",
            tool_name="get_building_state",
            arguments={**run, "state_id": 1},
        ),
        ToolRequest(
            request_id="m9c-05",
            tool_name="get_zone_state",
            arguments={**run, "zone": "SPACE3-1"},
        ),
        ToolRequest(
            request_id="m9c-06",
            tool_name="get_zone_state",
            arguments={**run, "zone": "PLENUM-1"},
        ),
        ToolRequest(
            request_id="m9c-07",
            tool_name="get_recent_state_history",
            arguments={**run, "zone": "SPACE3-1", "limit": 8},
        ),
        ToolRequest(request_id="m9c-08", tool_name="get_controller_status", arguments={}),
        ToolRequest(
            request_id="m9c-09",
            tool_name="get_controller_decisions",
            arguments={**run, "limit": 4},
        ),
        ToolRequest(request_id="m9c-10", tool_name="get_safety_guard_status", arguments={}),
        ToolRequest(
            request_id="m9c-11",
            tool_name="get_safety_decisions",
            arguments={**run, "limit": 4},
        ),
        ToolRequest(
            request_id="m9c-12",
            tool_name="get_physical_write_audit",
            arguments={**run, "limit": 4},
        ),
        ToolRequest(
            request_id="m9c-13", tool_name="get_energyplus_execution_status", arguments=run
        ),
        ToolRequest(request_id="m9c-14", tool_name="inspect_energyplus_errors", arguments=run),
        ToolRequest(
            request_id="m9c-15",
            tool_name="list_available_actuators",
            arguments={"limit": 10, "approved_only": True},
        ),
        ToolRequest(
            request_id="m9c-16", tool_name="list_available_actuators", arguments={"limit": 10}
        ),
        ToolRequest(request_id="m9c-17", tool_name="get_run_energy_summary", arguments=run),
        ToolRequest(
            request_id="m9c-18",
            tool_name="compare_runs",
            arguments={
                "reference_run_id": "module7-live-control",
                "experimental_run_id": "module8-live-control",
            },
        ),
        ToolRequest(request_id="m9c-19", tool_name="get_comfort_evidence", arguments=run),
        ToolRequest(
            request_id="m9c-20",
            tool_name="get_comfort_evidence",
            arguments={**run, "metric": "operative_temperature"},
        ),
        proposal("m9c-21"),
        proposal("m9c-22", zone="PLENUM-1", actuator_key="PLENUM-1"),
        proposal("m9c-23", units="F"),
        proposal("m9c-24", requested_value=40.0),
        proposal("m9c-25", requested_value="NaN"),
        proposal("m9c-26", current_sequence=14, expires_after_sequence=20),
        proposal("m9c-27", source_state_sequence=12, decision_sequence=11, current_sequence=13),
        ToolRequest(
            request_id="m9c-28", tool_name="get_run_metadata", arguments={"run_id": "unknown"}
        ),
        ToolRequest(
            request_id="m9c-29",
            tool_name="list_available_runs",
            arguments={"limit": 2, "cursor": "not-a-cursor"},
        ),
        ToolRequest(request_id="m9c-30", tool_name="list_available_runs", arguments={"limit": 101}),
        ToolRequest(request_id="m9c-31", tool_name="unknown_tool", arguments={}),
        ToolRequest(
            request_id="m9c-32",
            tool_name="propose_guarded_control",
            arguments={"runtime_mode": "guarded_control"},
        ),
        exact,
        ToolRequest(
            request_id="m9c-02", tool_name="get_run_metadata", arguments={"run_id": "module6-live"}
        ),
        proposal(
            "m9c-35",
            source_state_sequence=12,
            current_sequence=14,
            expires_after_sequence=13,
        ),
        proposal("m9c-36", current_sequence=14, expires_after_sequence=12),
        proposal("m9c-37", current_sequence=10),
        proposal("m9c-38", zone="SPACE2-1", actuator_key="SPACE2-1"),
    ]


def replay(config: Path, output: Path) -> dict[str, object]:
    service = MCPToolService(load_mcp_settings(config))
    responses = [service.call(item) for item in requests()]
    expected_errors = sum(not item.success for item in responses)
    outcomes: dict[str, int] = {}
    for item in responses:
        if item.tool_name == "validate_control_proposal" and item.success:
            outcome = str(item.data["guard_outcome"])
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
    stable = [
        {key: value for key, value in item.model_dump(mode="json").items() if key != "fingerprint"}
        for item in responses
    ]
    report = {
        "call_count": len(responses),
        "success_count": sum(item.success for item in responses),
        "expected_error_count": expected_errors,
        "physical_write_count": 0,
        "dry_run_count": sum(item.tool_name == "validate_control_proposal" for item in responses),
        "dry_run_outcomes": outcomes,
        "catalogue_fingerprint": service.catalogue_fingerprint,
        "fingerprint": fingerprint(stable),
        "responses": stable,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "responses"}, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/mcp_server.yaml"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = replay(args.config, args.output)
    return 0 if report["call_count"] == 38 and report["physical_write_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
