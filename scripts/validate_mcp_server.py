"""Validate Module 9 catalogue, replay, smoke, and audit evidence."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mcp_server.config import load_mcp_settings  # noqa: E402
from src.mcp_server.registry import build_registry, catalogue_fingerprint  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/mcp_server.yaml"))
    parser.add_argument(
        "--replay", type=Path, default=Path("data/output/module_9_mcp/replay/verify_1.json")
    )
    parser.add_argument(
        "--smoke", type=Path, default=Path("data/output/module_9_mcp/mcp_server_smoke.json")
    )
    args = parser.parse_args()
    settings = load_mcp_settings(args.config)
    tools = build_registry(settings.control_tools_enabled)
    replay = json.loads(args.replay.read_text(encoding="utf-8"))
    smoke = json.loads(args.smoke.read_text(encoding="utf-8"))
    connection = sqlite3.connect(settings.audit_database)
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    audit_count = connection.execute("SELECT COUNT(*) FROM mcp_tool_calls").fetchone()[0]
    schema = int(
        connection.execute(
            "SELECT value FROM schema_metadata WHERE key='schema_version'"
        ).fetchone()[0]
    )
    connection.close()
    checks = {
        "tool_count": len(tools) == 44,
        "enabled_count": sum(tool.enabled for tool in tools) == 43,
        "control_disabled": not tools[-1].enabled,
        "catalogue_fingerprint": len(replay["catalogue_fingerprint"]) == 64
        and len(catalogue_fingerprint(tools)) == 64,
        "replay_counts": replay["call_count"] == len(replay["responses"])
        and replay["success_count"] + replay["expected_error_count"] == replay["call_count"]
        and replay["physical_write_count"] == 0,
        "smoke": smoke["status"] == "PASS" and smoke["physical_write_count"] == 0,
        "audit_records": audit_count >= 24,
        "database_schema": schema == 4,
        "database_integrity": integrity == "ok",
        "foreign_keys": not foreign_keys,
    }
    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "audit_record_count": audit_count,
        "database_integrity": integrity,
        "foreign_key_violation_count": len(foreign_keys),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
