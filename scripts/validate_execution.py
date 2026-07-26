"""Validate persisted Module 14 boundaries without starting EnergyPlus."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.execution.config import load_execution_settings
from src.mcp_server.config import load_mcp_settings
from src.mcp_server.registry import build_registry
from src.storage.execution_schema import migrate

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    settings = load_execution_settings(ROOT / "config/execution_orchestrator.yaml")
    mcp = load_mcp_settings(ROOT / "config/mcp_server.yaml")
    tools = build_registry(False)
    with sqlite3.connect(settings.database) as connection:
        migrate(connection)
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "execution_approvals",
                "execution_sessions",
                "execution_actions",
                "execution_state_transitions",
                "execution_writer_attempts",
                "execution_fallback_events",
                "execution_resets",
                "execution_run_comparisons",
                "simulation_reconciliation",
            )
        }
    checks = {
        "schema_9": version == 9,
        "integrity": integrity == "ok",
        "foreign_keys": not foreign_keys,
        "catalogue_v5_44": mcp.catalogue_version == 5 and len(tools) == 44,
        "four_read_only_tools": all(
            next(x for x in tools if x.name == name).classification.value == "READ_ONLY"
            for name in (
                "get_execution_approval_status",
                "get_plan_execution_status",
                "get_plan_execution_audit",
                "compare_execution_runs",
            )
        ),
        "control_disabled": not next(
            x for x in tools if x.name == "propose_guarded_control"
        ).enabled,
        "no_execution_trigger": not any(
            "execute" in x.name or "start_execution" in x.name for x in tools
        ),
    }
    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "database_counts": counts,
        "mcp_tool_count": len(tools),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
