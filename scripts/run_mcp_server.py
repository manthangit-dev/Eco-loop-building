"""Launch the local-only ThermoLedger MCP server over stdio."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server.fastmcp import FastMCP  # noqa: E402
from src.mcp_server.config import load_mcp_settings  # noqa: E402
from src.mcp_server.models import ToolRequest  # noqa: E402
from src.mcp_server.service import MCPToolService  # noqa: E402


def build_server() -> FastMCP:
    root = Path(__file__).resolve().parents[1]
    service = MCPToolService(load_mcp_settings(root / "config/mcp_server.yaml"))
    server = FastMCP("ThermoLedger deterministic building tools")
    for definition in service.registry:

        def make_handler(tool_name: str) -> Any:
            async def handler(arguments: dict[str, Any], request_id: str) -> dict[str, Any]:
                request = ToolRequest(
                    request_id=request_id, tool_name=tool_name, arguments=arguments
                )
                return service.call(request).model_dump(mode="json")

            handler.__name__ = tool_name
            handler.__doc__ = service.definitions[tool_name].purpose
            return handler

        server.tool(name=definition.name, description=definition.purpose)(
            make_handler(definition.name)
        )
    return server


if __name__ == "__main__":
    build_server().run(transport="stdio")
