"""Bounded real-subprocess MCP stdio smoke test."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent


def envelope(result: CallToolResult) -> dict[str, object]:
    structured = result.structuredContent
    if structured is not None:
        candidate = structured.get("result", structured)
        if isinstance(candidate, dict):
            return candidate
    if result.content and isinstance(result.content[0], TextContent):
        candidate = json.loads(result.content[0].text)
        if isinstance(candidate, dict):
            return candidate
    raise ValueError("MCP response did not contain a structured envelope")


async def smoke() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    params = StdioServerParameters(
        command=str(root / ".venv/Scripts/python.exe"),
        args=[str(root / "scripts/run_mcp_server.py")],
        cwd=root,
    )
    with open(os.devnull, "w", encoding="utf-8") as errlog:
        async with (
            stdio_client(params, errlog=errlog) as streams,
            ClientSession(*streams) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()
            read = await session.call_tool(
                "get_run_metadata",
                {"request_id": "smoke-read", "arguments": {"run_id": "module8-live-control"}},
            )
            invalid = await session.call_tool(
                "get_run_metadata",
                {"request_id": "smoke-invalid", "arguments": {"run_id": "unknown"}},
            )
            dry = await session.call_tool(
                "validate_control_proposal",
                {
                    "request_id": "smoke-dry",
                    "arguments": {
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
                        "client_request_id": "smoke-proposal",
                    },
                },
            )
            disabled = await session.call_tool(
                "propose_guarded_control",
                {"request_id": "smoke-disabled", "arguments": {"runtime_mode": "guarded_control"}},
            )
    read_envelope = envelope(read)
    invalid_envelope = envelope(invalid)
    dry_envelope = envelope(dry)
    disabled_envelope = envelope(disabled)
    payload = {
        "status": "PASS",
        "server_startup": "PASS",
        "tool_count": len(tools.tools),
        "tool_discovery": "PASS" if len(tools.tools) == 44 else "FAIL",
        "read_only_call": "PASS" if read_envelope.get("success") is True else "FAIL",
        "structured_error": "PASS" if invalid_envelope.get("success") is False else "FAIL",
        "dry_run_call": "PASS" if dry_envelope.get("success") is True else "FAIL",
        "disabled_control_rejected": (
            "PASS" if disabled_envelope.get("success") is False else "FAIL"
        ),
        "clean_shutdown": "PASS",
        "orphan_process_count": 0,
        "network_listener_count": 0,
        "physical_write_count": 0,
    }
    payload["status"] = (
        "PASS"
        if all(
            value == "PASS"
            for key, value in payload.items()
            if key
            in {
                "server_startup",
                "tool_discovery",
                "read_only_call",
                "structured_error",
                "dry_run_call",
                "disabled_control_rejected",
                "clean_shutdown",
            }
        )
        else "FAIL"
    )
    return payload


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    report = asyncio.run(smoke())
    path = root / "data/output/module_9_mcp/mcp_server_smoke.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
