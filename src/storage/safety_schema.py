"""Additive Module 8 schema-v3 migration."""

import sqlite3

SAFETY_DATABASE_SCHEMA_VERSION = 3

SAFETY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS safety_guard_decisions (
 guard_decision_id TEXT PRIMARY KEY, command_id TEXT NOT NULL, run_id TEXT NOT NULL,
 environment_id TEXT NOT NULL, source_state_sequence INTEGER NOT NULL,
 actuator_identity TEXT NOT NULL, requested_value TEXT, applied_value REAL,
 outcome TEXT NOT NULL, reason_code TEXT NOT NULL, previous_safe_value REAL,
 safety_schema_version INTEGER NOT NULL, current_sequence INTEGER NOT NULL,
 fingerprint TEXT NOT NULL UNIQUE, persisted_order INTEGER NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS safety_guard_violations (
 violation_id TEXT PRIMARY KEY,
 guard_decision_id TEXT NOT NULL REFERENCES safety_guard_decisions(guard_decision_id),
 violation_category TEXT NOT NULL, reason_code TEXT NOT NULL,
 expected_value TEXT, observed_value TEXT, details_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS guarded_commands (
 command_id TEXT PRIMARY KEY, guard_decision_id TEXT NOT NULL UNIQUE
 REFERENCES safety_guard_decisions(guard_decision_id), run_id TEXT NOT NULL,
 environment_id TEXT NOT NULL, payload_json TEXT NOT NULL,
 expires_after_sequence INTEGER NOT NULL, physical_submission_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS physical_write_attempts (
 attempt_id INTEGER PRIMARY KEY, guarded_command_id TEXT REFERENCES guarded_commands(command_id),
 guard_decision_id TEXT REFERENCES safety_guard_decisions(guard_decision_id),
 operation TEXT NOT NULL, permitted INTEGER NOT NULL, applied_value REAL,
 callback_context_json TEXT NOT NULL, reason_code TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_guard_run_command ON safety_guard_decisions(run_id,command_id);
CREATE INDEX IF NOT EXISTS idx_guard_reason ON safety_guard_decisions(reason_code);
"""


def migrate_safety_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys=ON")
    if connection.in_transaction:
        connection.commit()
    connection.execute("BEGIN")
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)"
        )
        row = connection.execute(
            "SELECT value FROM schema_metadata WHERE key='schema_version'"
        ).fetchone()
        version = 2 if row is None else int(row[0])
        if version > SAFETY_DATABASE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported future schema version {version}.")
        connection.executescript(SAFETY_SCHEMA_SQL)
        connection.execute(
            "INSERT OR REPLACE INTO schema_metadata VALUES('schema_version',?)",
            (str(SAFETY_DATABASE_SCHEMA_VERSION),),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
