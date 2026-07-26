"""Read-only predefined Module 8 audit queries."""

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/output/module_8_safety_guard/live_control/current/safety_guard.db"),
    )
    parser.add_argument(
        "--query", choices=("summary", "recent", "violations", "writes"), default="summary"
    )
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    connection = sqlite3.connect(f"file:{args.database.resolve()}?mode=ro", uri=True)
    queries = {
        "summary": (
            "SELECT outcome,reason_code,COUNT(*) FROM safety_guard_decisions "
            "GROUP BY outcome,reason_code"
        ),
        "recent": (
            "SELECT guard_decision_id,command_id,outcome,reason_code "
            "FROM safety_guard_decisions ORDER BY persisted_order DESC LIMIT ?"
        ),
        "violations": (
            "SELECT violation_category,reason_code,COUNT(*) FROM safety_guard_violations "
            "GROUP BY violation_category,reason_code LIMIT ?"
        ),
        "writes": (
            "SELECT operation,permitted,reason_code,COUNT(*) FROM physical_write_attempts "
            "GROUP BY operation,permitted,reason_code LIMIT ?"
        ),
    }
    parameters = () if args.query == "summary" else (max(1, min(args.limit, 100)),)
    for row in connection.execute(queries[args.query], parameters):
        print(" | ".join(str(value) for value in row))
    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
