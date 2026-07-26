"""Call one real local stdio MCP tool with a stable JSON interface."""

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from mcp.types import TextContent  # noqa: E402


async def invoke(tool: str, arguments: dict[str, Any], request_id: str) -> dict[str, Any]:
    params = StdioServerParameters(
        command=str(ROOT / ".venv/Scripts/python.exe"),
        args=[str(ROOT / "scripts/run_mcp_server.py")],
        cwd=ROOT,
    )
    with open(os.devnull, "w", encoding="utf-8") as errlog:
        async with (
            stdio_client(params, errlog=errlog) as streams,
            ClientSession(*streams) as session,
        ):
            await session.initialize()
            result = await session.call_tool(
                tool, {"request_id": request_id, "arguments": arguments}
            )
    if result.structuredContent:
        candidate = result.structuredContent.get("result", result.structuredContent)
        if isinstance(candidate, dict):
            return candidate
    if result.content and isinstance(result.content[0], TextContent):
        try:
            candidate = json.loads(result.content[0].text)
            if isinstance(candidate, dict):
                return candidate
        except json.JSONDecodeError:
            if result.isError:
                return {
                    "request_id": request_id,
                    "tool_name": tool,
                    "success": False,
                    "errors": [
                        {"code": "mcp_transport_tool_error", "message": result.content[0].text}
                    ],
                    "provenance": {"transport": "local_stdio"},
                    "physical_write_performed": False,
                }
    raise ValueError("MCP server returned no structured envelope")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", required=True)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--input-file", type=Path)
    inputs.add_argument("--input-json")
    parser.add_argument("--request-id")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--config", type=Path, help="Reserved canonical config override")
    parser.add_argument("--no-audit", action="store_true", help="Rejected for safety")
    args = parser.parse_args()
    if args.no_audit:
        print("--no-audit is not supported by the real stdio demo", file=sys.stderr)
        return 2
    try:
        raw = args.input_file.read_text(encoding="utf-8") if args.input_file else args.input_json
        arguments = json.loads(str(raw))
        if not isinstance(arguments, dict):
            raise ValueError("input must be a JSON object")
        digest = hashlib.sha256(json.dumps(arguments, sort_keys=True).encode()).hexdigest()[:16]
        request_id = args.request_id or f"manual-{args.tool}-{digest}"
        result = asyncio.run(invoke(args.tool, arguments, request_id))
        print(json.dumps(result, indent=2 if args.pretty else None, allow_nan=False))
        return 0 if result.get("success") is True else 3
    except Exception as exc:
        print(f"MCP call failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
