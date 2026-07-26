"""Validate Module 10 configuration, replay, persistence, and no-write invariants."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.scenarios import SCENARIOS
from src.llm.config import load_llm_settings


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    settings = load_llm_settings(Path("config/llm_supervisor.yaml"))
    replay = json.loads((settings.output_root / "mock/mock_1.json").read_text(encoding="utf-8"))
    connection = sqlite3.connect(settings.database)
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    schema = connection.execute(
        "SELECT value FROM schema_metadata WHERE key='schema_version'"
    ).fetchone()[0]
    sessions = connection.execute("SELECT COUNT(*) FROM llm_sessions").fetchone()[0]
    writes = connection.execute(
        "SELECT COALESCE(SUM(physical_write_performed),0) FROM llm_sessions"
    ).fetchone()[0]
    tool_calls = connection.execute(
        "SELECT COALESCE(SUM(tool_call_count),0) FROM llm_sessions"
    ).fetchone()[0]
    connection.close()
    checks = {
        "schema": schema == "5",
        "integrity": integrity == "ok",
        "foreign_keys": not foreign_keys,
        "scenario_count": len(SCENARIOS) == replay["scenario_count"] == 50,
        "mock_pass": replay["pass_count"] == 50,
        "zero_writes": writes == replay["physical_write_count"] == 0,
        "bounded": settings.maximum_tool_calls <= 8,
    }
    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "session_count": sessions,
        "mcp_tool_call_count": tool_calls,
        "database_integrity": integrity,
        "foreign_key_violation_count": len(foreign_keys),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
