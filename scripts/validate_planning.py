"""Validate Module 11 artifacts and schema-v6 persistence."""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.planning.config import load_planning_settings

from scripts.planning_common import build

if __name__ == "__main__":
    context, plans = build()
    settings = load_planning_settings(Path("config/planning.yaml"))
    c = sqlite3.connect(settings.database)
    integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
    foreign = c.execute("PRAGMA foreign_key_check").fetchall()
    version = c.execute("SELECT value FROM schema_metadata WHERE key='schema_version'").fetchone()[
        0
    ]
    counts = {
        table: c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "planning_contexts",
            "candidate_plans",
            "candidate_actions",
            "planning_sessions",
        )
    }
    c.close()
    ok = (
        version == "6"
        and integrity == "ok"
        and not foreign
        and len(plans) >= 4
        and context.prohibited_future_source_count == 0
    )
    print(
        json.dumps(
            {
                "status": "PASS" if ok else "FAIL",
                "schema_version": int(version),
                "database_integrity": integrity,
                "foreign_key_violations": len(foreign),
                "counts": counts,
                "candidate_count": len(plans),
                "eligible_count": sum(p.eligible for p in plans),
                "context_fingerprint": context.context_fingerprint,
            },
            indent=2,
        )
    )
    raise SystemExit(0 if ok else 1)
