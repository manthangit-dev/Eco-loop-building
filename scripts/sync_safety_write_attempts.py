"""Persist traced guarded write attempts from a completed live run."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.storage.safety_store import SafetyStore  # noqa: E402


def sync(directory: Path) -> int:
    controller = sqlite3.connect(
        f"file:{(directory / 'thermoledger_state.db').resolve()}?mode=ro", uri=True
    )
    rows = controller.execute(
        "SELECT command_id,event_type,value_celsius,detail,state_sequence "
        "FROM controller_events ORDER BY id"
    ).fetchall()
    controller.close()
    safety_path = directory / "safety_guard.db"
    with SafetyStore(safety_path, directory.parents[2]) as store:
        existing = int(
            store.connection.execute("SELECT COUNT(*) FROM physical_write_attempts").fetchone()[0]
        )
        store.connection.execute("BEGIN")
        for command_id, operation, value, detail, sequence in rows[existing:]:
            guard_id = str(detail).removeprefix("Guard decision ")
            if command_id is None:
                found = store.connection.execute(
                    "SELECT command_id FROM guarded_commands WHERE guard_decision_id=?", (guard_id,)
                ).fetchone()
                command_id = None if found is None else str(found[0])
            store.connection.execute(
                """INSERT INTO physical_write_attempts(guarded_command_id,
                guard_decision_id,operation,permitted,applied_value,
                callback_context_json,reason_code) VALUES(?,?,?,?,?,?,?)""",
                (
                    command_id,
                    guard_id,
                    str(operation),
                    1,
                    value,
                    '{"source":"completed_live_trace","state_sequence":' + str(int(sequence)) + "}",
                    "guarded",
                ),
            )
        store.connection.execute(
            """UPDATE guarded_commands SET physical_submission_status='SUBMITTED'
            WHERE command_id IN (SELECT guarded_command_id FROM physical_write_attempts
            WHERE permitted=1)"""
        )
        store.connection.commit()
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--directory",
        type=Path,
        default=Path("data/output/module_8_safety_guard/live_control/current"),
    )
    args = parser.parse_args()
    count = sync(args.directory)
    print(f"Persisted physical write attempts: {count}")
    return 0 if count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
