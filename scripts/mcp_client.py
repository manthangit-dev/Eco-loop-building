"""Local MCP inspection client using the official stdio client."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run(action: str, tool: str | None, arguments: dict[str, object]) -> object:
    root = Path(__file__).resolve().parents[1]
    params = StdioServerParameters(
        command=str(root / ".venv/Scripts/python.exe"),
        args=[str(root / "scripts/run_mcp_server.py")],
        cwd=root,
    )
    async with stdio_client(params) as streams, ClientSession(*streams) as session:
        await session.initialize()
        if action == "list":
            list_result = await session.list_tools()
            return [
                {
                    "name": item.name,
                    "description": item.description,
                    "inputSchema": item.inputSchema,
                }
                for item in list_result.tools
            ]
        if tool is None:
            raise ValueError("--tool is required for call")
        call_result = await session.call_tool(tool, arguments)
        return call_result.model_dump(mode="json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("list", "call"))
    parser.add_argument("--tool")
    parser.add_argument("--arguments", default="{}")
    args = parser.parse_args()
    arguments = json.loads(args.arguments)
    print(json.dumps(asyncio.run(run(args.action, args.tool, arguments)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
