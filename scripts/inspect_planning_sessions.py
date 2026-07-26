"""Inspect bounded planning persistence counts."""

import json
import sqlite3
from pathlib import Path

if __name__ == "__main__":
    c = sqlite3.connect(Path("data/output/module_11_planning/planning.db"))
    tables = (
        "planning_contexts",
        "candidate_plans",
        "candidate_actions",
        "planning_sessions",
        "plan_selections",
    )
    print(
        json.dumps(
            {table: c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables},
            indent=2,
        )
    )
    c.close()
