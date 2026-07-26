"""Bounded MCP audit inspection for users and the current demo."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, default=ROOT / "data/output/module_9_mcp/mcp_audit.db"
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    try:
        if not args.database.exists():
            raise FileNotFoundError(f"audit database not found: {args.database}")
        limit = 1 if args.latest else min(max(args.limit, 1), 100)
        connection = sqlite3.connect(f"file:{args.database.resolve()}?mode=ro", uri=True)
        sql = """SELECT tool_call_id,tool_name,success,run_id,response_json
        FROM mcp_tool_calls WHERE (? IS NULL OR run_id=?)
        ORDER BY deterministic_order DESC LIMIT ?"""
        rows = []
        for call_id, tool, success, run_id, response_json in connection.execute(
            sql, (args.run_id, args.run_id, limit)
        ):
            response = json.loads(response_json)
            errors = response.get("errors", [])
            data = response.get("data") or {}
            physical_count = data.get("physical_write_count", 0) if isinstance(data, dict) else 0
            rows.append(
                {
                    "tool_call_id": call_id,
                    "tool": tool,
                    "success": bool(success),
                    "run_id": run_id,
                    "error": errors[0]["code"] if errors else None,
                    "physical_submission_requested": tool == "propose_guarded_control",
                    "physical_submission_performed": bool(physical_count),
                }
            )
        connection.close()
        if args.json:
            print(json.dumps({"count": len(rows), "records": rows}, indent=2))
        else:
            for row in rows:
                print(" | ".join(f"{key}={value}" for key, value in row.items()))
        return 0
    except Exception as exc:
        print(f"MCP audit inspection failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
