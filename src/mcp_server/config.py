"""Strict local-only MCP configuration."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


@dataclass(frozen=True)
class MCPSettings:
    root: Path
    schema_version: int
    catalogue_version: int
    implementation_version: str
    transport: str
    control_tools_enabled: bool
    control_runtime_mode: str
    default_rows: int
    maximum_rows: int
    maximum_history_points: int
    maximum_error_entries: int
    timeout_seconds: int
    output_root: Path
    audit_database: Path
    runs: tuple[tuple[str, Path], ...]

    def run_path(self, run_id: str) -> Path:
        for known_id, path in self.runs:
            if known_id == run_id:
                return path
        raise KeyError(run_id)


def load_mcp_settings(path: Path) -> MCPSettings:
    root = path.resolve().parents[1]
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    mcp = raw["mcp"]
    limits = raw["limits"]
    storage = raw["storage"]
    if int(mcp["schema_version"]) != 1:
        raise ValueError("Unsupported MCP schema version.")
    if mcp["transport"] != "stdio" or not mcp["local_only"]:
        raise ValueError("Module 9 permits local stdio transport only.")
    if mcp.get("host") is not None or mcp.get("port") is not None:
        raise ValueError("Listening network configuration is forbidden.")
    default_rows, maximum_rows = int(limits["default_rows"]), int(limits["maximum_rows"])
    timeout = int(limits["timeout_seconds"])
    if not 0 < default_rows <= maximum_rows <= 1000 or timeout < 0:
        raise ValueError("Invalid MCP limits.")
    output_root = (root / str(storage["output_root"])).resolve()
    runs = tuple((str(key), (root / str(value)).resolve()) for key, value in raw["runs"].items())
    if len({name for name, _ in runs}) != len(runs):
        raise ValueError("Duplicate run ID.")
    return MCPSettings(
        root,
        1,
        int(mcp["catalogue_version"]),
        str(mcp["implementation_version"]),
        "stdio",
        bool(mcp["control_tools_enabled"]),
        str(mcp["required_control_runtime_mode"]),
        default_rows,
        maximum_rows,
        int(limits["maximum_history_points"]),
        int(limits["maximum_error_entries"]),
        timeout,
        output_root,
        output_root / str(storage["audit_database"]),
        runs,
    )
