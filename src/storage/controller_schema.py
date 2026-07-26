"""Transactional Module 6 schema-v1 to Module 7 schema-v2 migration."""

import sqlite3

CONTROLLER_SCHEMA_VERSION = 2

CONTROLLER_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS controller_runs (
 run_id TEXT PRIMARY KEY, simulation_run_id TEXT NOT NULL, mode TEXT NOT NULL,
 status TEXT NOT NULL, started_at_utc TEXT NOT NULL, finished_at_utc TEXT,
 model_checksum TEXT NOT NULL, weather_checksum TEXT NOT NULL,
 expected_state_count INTEGER NOT NULL, state_count INTEGER NOT NULL DEFAULT 0,
 decision_count INTEGER NOT NULL DEFAULT 0, command_count INTEGER NOT NULL DEFAULT 0,
 set_call_count INTEGER NOT NULL DEFAULT 0, reset_count INTEGER NOT NULL DEFAULT 0,
 expiry_count INTEGER NOT NULL DEFAULT 0, rejected_count INTEGER NOT NULL DEFAULT 0,
 api_error_count INTEGER NOT NULL DEFAULT 0, callback_error_count INTEGER NOT NULL DEFAULT 0,
 actuator_access_count INTEGER NOT NULL DEFAULT 0, safety_guard_status TEXT NOT NULL,
 energy_saving_claim INTEGER NOT NULL DEFAULT 0 CHECK(energy_saving_claim=0)
);
CREATE TABLE IF NOT EXISTS control_decisions (
 decision_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES controller_runs(run_id),
 decision_sequence INTEGER NOT NULL, based_on_state_sequence INTEGER NOT NULL,
 based_on_state_fingerprint TEXT NOT NULL, created_at_utc TEXT NOT NULL,
 target_zone_id TEXT NOT NULL, target_zone_name TEXT NOT NULL,
 mode_before TEXT NOT NULL, mode_after TEXT NOT NULL, reason_code TEXT NOT NULL,
 explanation TEXT NOT NULL, occupancy REAL NOT NULL, zone_temperature_celsius REAL,
 baseline_setpoint_celsius REAL, requested_setpoint_celsius REAL,
 approved_setpoint_celsius REAL, clamped INTEGER NOT NULL, action_type TEXT NOT NULL,
 command_ttl INTEGER NOT NULL, intended_effective_sequence INTEGER NOT NULL,
 actuator_identity TEXT NOT NULL, shadow_mode INTEGER NOT NULL,
 safety_guard_status TEXT NOT NULL, validation_issues_json TEXT NOT NULL,
 UNIQUE(run_id,decision_sequence),
 CHECK(intended_effective_sequence > based_on_state_sequence)
);
CREATE TABLE IF NOT EXISTS control_commands (
 command_id TEXT PRIMARY KEY, decision_id TEXT NOT NULL REFERENCES control_decisions(decision_id),
 run_id TEXT NOT NULL REFERENCES controller_runs(run_id), target_zone_id TEXT NOT NULL,
 target_zone_name TEXT NOT NULL, actuator_identity TEXT NOT NULL, setpoint_celsius REAL,
 issued_from_sequence INTEGER NOT NULL, valid_from_sequence INTEGER NOT NULL,
 expires_after_sequence INTEGER NOT NULL, reset_required INTEGER NOT NULL,
 mode TEXT NOT NULL, reason TEXT NOT NULL, shadow_mode INTEGER NOT NULL,
 fingerprint TEXT NOT NULL, CHECK(valid_from_sequence > issued_from_sequence),
 CHECK(expires_after_sequence >= valid_from_sequence)
);
CREATE TABLE IF NOT EXISTS controller_events (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES controller_runs(run_id),
 command_id TEXT REFERENCES control_commands(command_id), event_type TEXT NOT NULL,
 state_sequence INTEGER NOT NULL, simulation_timestamp TEXT NOT NULL,
 value_celsius REAL, detail TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS command_outcomes (
 outcome_id TEXT PRIMARY KEY, command_id TEXT NOT NULL REFERENCES control_commands(command_id),
 observed_state_sequence INTEGER NOT NULL, event_type TEXT NOT NULL,
 effective_setpoint_celsius REAL, zone_temperature_celsius REAL, occupancy REAL NOT NULL,
 outdoor_temperature_celsius REAL NOT NULL, facility_electricity_raw_j REAL NOT NULL,
 hvac_electricity_raw_j REAL NOT NULL, association_label TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS zone_controller_memory_snapshots (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES controller_runs(run_id),
 state_sequence INTEGER NOT NULL, zone_id TEXT NOT NULL, memory_json TEXT NOT NULL,
 UNIQUE(run_id,state_sequence,zone_id)
);
CREATE INDEX IF NOT EXISTS idx_decisions_run_state
ON control_decisions(run_id,based_on_state_sequence);
CREATE INDEX IF NOT EXISTS idx_decisions_run_zone ON control_decisions(run_id,target_zone_id);
CREATE INDEX IF NOT EXISTS idx_decisions_run_reason ON control_decisions(run_id,reason_code);
CREATE INDEX IF NOT EXISTS idx_commands_run_sequence
ON control_commands(run_id,issued_from_sequence);
CREATE INDEX IF NOT EXISTS idx_events_run_command ON controller_events(run_id,command_id);
"""


def migrate_controller_schema(
    connection: sqlite3.Connection, *, allow_safety_schema: bool = False
) -> None:
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
        version = 1 if row is None else int(row[0])
        maximum_version = 3 if allow_safety_schema else CONTROLLER_SCHEMA_VERSION
        if version > maximum_version:
            raise ValueError(f"Unsupported future schema version {version}.")
        connection.executescript(CONTROLLER_SCHEMA_SQL)
        connection.execute(
            "INSERT OR REPLACE INTO schema_metadata(key,value) VALUES('schema_version',?)",
            (str(max(version, CONTROLLER_SCHEMA_VERSION)),),
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
