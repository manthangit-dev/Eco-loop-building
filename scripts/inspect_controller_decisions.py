"""Inspect Module 7 controller records through predefined read-only queries."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.storage.controller_queries import open_controller_read_only, rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument(
        "--query",
        choices=("recent", "zone", "reason", "commands", "resets", "rejected", "outcomes"),
        default="recent",
    )
    parser.add_argument("--value", default="")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    with open_controller_read_only(args.database) as connection:
        runs = connection.execute(
            "SELECT * FROM controller_runs ORDER BY started_at_utc"
        ).fetchall()
        run_id = str(runs[-1]["run_id"]) if runs else ""
        selected = rows(connection, args.query, run_id, args.limit, args.value)
        payload = {
            "runs": [dict(row) for row in runs],
            "results": [dict(row) for row in selected],
            "integrity": connection.execute("PRAGMA integrity_check").fetchone()[0],
            "foreign_key_violations": len(
                connection.execute("PRAGMA foreign_key_check").fetchall()
            ),
        }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
