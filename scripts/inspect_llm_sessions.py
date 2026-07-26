"""Bounded read-only LLM session audit inspection."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, default=ROOT / "data/output/module_10_llm/llm_audit.db"
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--session-id")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    try:
        if not args.database.exists():
            raise FileNotFoundError(f"LLM database not found: {args.database}")
        limit = 1 if args.latest else min(max(args.limit, 1), 100)
        connection = sqlite3.connect(f"file:{args.database.resolve()}?mode=ro", uri=True)
        rows = [
            {
                "session_id": row[0],
                "objective": row[1],
                "provider": row[2],
                "model": row[3],
                "tool_call_count": row[4],
                "correction_count": row[5],
                "policy_events": row[6],
                "status": row[7],
                "physical_write_performed": bool(row[8]),
            }
            for row in connection.execute(
                """SELECT s.session_id,s.objective_type,s.provider,s.model,s.tool_call_count,
                s.correction_count,(SELECT COUNT(*) FROM llm_policy_events p
                WHERE p.session_id=s.session_id),s.status,s.physical_write_performed
                FROM llm_sessions s WHERE (? IS NULL OR s.session_id=?)
                AND (? IS NULL OR s.run_id=?) ORDER BY s.rowid DESC LIMIT ?""",
                (args.session_id, args.session_id, args.run_id, args.run_id, limit),
            )
        ]
        connection.close()
        if args.json:
            print(json.dumps({"count": len(rows), "sessions": rows}, indent=2))
        else:
            for row in rows:
                print(" | ".join(f"{key}={value}" for key, value in row.items()))
        return 0
    except Exception as exc:
        print(f"LLM audit inspection failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
