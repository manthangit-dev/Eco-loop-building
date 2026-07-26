"""Predefined read-only Module 7 queries."""

import sqlite3
from pathlib import Path


def open_controller_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def rows(
    connection: sqlite3.Connection, kind: str, run_id: str, limit: int = 20, value: str = ""
) -> list[sqlite3.Row]:
    queries = {
        "recent": (
            """SELECT * FROM control_decisions WHERE run_id=?
               ORDER BY decision_sequence DESC LIMIT ?""",
            (run_id, limit),
        ),
        "zone": (
            """SELECT * FROM control_decisions WHERE run_id=? AND target_zone_id=?
               ORDER BY decision_sequence DESC LIMIT ?""",
            (run_id, value, limit),
        ),
        "reason": (
            """SELECT * FROM control_decisions WHERE run_id=? AND reason_code=?
               ORDER BY decision_sequence DESC LIMIT ?""",
            (run_id, value, limit),
        ),
        "commands": (
            """SELECT * FROM control_commands WHERE run_id=?
               ORDER BY issued_from_sequence DESC LIMIT ?""",
            (run_id, limit),
        ),
        "resets": (
            """SELECT * FROM controller_events WHERE run_id=? AND event_type='RESET'
               ORDER BY id DESC LIMIT ?""",
            (run_id, limit),
        ),
        "rejected": (
            """SELECT * FROM control_decisions WHERE run_id=? AND action_type='REJECT'
               ORDER BY decision_sequence DESC LIMIT ?""",
            (run_id, limit),
        ),
        "outcomes": (
            """SELECT o.* FROM command_outcomes o JOIN control_commands c
               ON c.command_id=o.command_id WHERE c.run_id=?
               ORDER BY observed_state_sequence DESC LIMIT ?""",
            (run_id, limit),
        ),
    }
    sql, parameters = queries[kind]
    return connection.execute(sql, parameters).fetchall()
