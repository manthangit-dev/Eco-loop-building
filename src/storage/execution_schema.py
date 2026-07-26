"""Additive schema-10 context-aligned execution migration."""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 10

DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS execution_approvals (
 approval_id TEXT PRIMARY KEY, approval_json TEXT NOT NULL, execution_mode TEXT NOT NULL,
 plan_id TEXT NOT NULL, expires_at TEXT NOT NULL, status TEXT NOT NULL,
 consumed_session_id TEXT, approval_fingerprint TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS execution_sessions (
 session_id TEXT PRIMARY KEY, approval_id TEXT NOT NULL REFERENCES execution_approvals(approval_id),
 mode TEXT NOT NULL, state TEXT NOT NULL, physical_set_calls INTEGER NOT NULL,
 physical_reset_calls INTEGER NOT NULL, fallback_count INTEGER NOT NULL, report_json TEXT NOT NULL,
 fingerprint TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS execution_state_transitions (
 session_id TEXT NOT NULL REFERENCES execution_sessions(session_id), sequence INTEGER NOT NULL,
 from_state TEXT NOT NULL, to_state TEXT NOT NULL, reason_code TEXT NOT NULL,
 PRIMARY KEY(session_id, sequence));
CREATE TABLE IF NOT EXISTS execution_actions (
 session_id TEXT NOT NULL REFERENCES execution_sessions(session_id), action_id TEXT NOT NULL,
 action_sequence INTEGER NOT NULL, requested_value REAL NOT NULL,
 guard_outcome TEXT NOT NULL, writer_status TEXT NOT NULL, terminal_status TEXT NOT NULL,
 PRIMARY KEY(session_id, action_id));
CREATE TABLE IF NOT EXISTS execution_writer_attempts (
 attempt_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES execution_sessions(session_id),
 action_id TEXT NOT NULL, operation TEXT NOT NULL, permitted INTEGER NOT NULL,
 result TEXT NOT NULL, uncertain_status INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS execution_fallback_events (
 session_id TEXT NOT NULL REFERENCES execution_sessions(session_id), sequence INTEGER NOT NULL,
 trigger TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(session_id, sequence));
CREATE TABLE IF NOT EXISTS execution_resets (
 session_id TEXT NOT NULL REFERENCES execution_sessions(session_id), sequence INTEGER NOT NULL,
 reason TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(session_id, sequence));
CREATE TABLE IF NOT EXISTS execution_run_comparisons (
 comparison_id TEXT PRIMARY KEY, native_run_id TEXT NOT NULL, shadow_run_id TEXT NOT NULL,
 live_run_id TEXT NOT NULL, compatibility_status TEXT NOT NULL, metrics_json TEXT NOT NULL,
 fingerprint TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS simulation_reconciliation (
 reconciliation_id TEXT NOT NULL, timestep_sequence INTEGER NOT NULL, plan_id TEXT NOT NULL,
 rollout_id TEXT NOT NULL, live_run_id TEXT NOT NULL, predicted_temperature REAL NOT NULL,
 simulated_temperature REAL NOT NULL, prediction_error REAL NOT NULL,
 lower_bound REAL NOT NULL, upper_bound REAL NOT NULL, interval_covered INTEGER NOT NULL,
 predicted_risk INTEGER NOT NULL, simulated_risk INTEGER NOT NULL,
 PRIMARY KEY(reconciliation_id, timestep_sequence));
CREATE TABLE IF NOT EXISTS execution_context_bindings (
 binding_id TEXT PRIMARY KEY, approval_id TEXT NOT NULL REFERENCES execution_approvals(approval_id),
 planning_context_id TEXT NOT NULL, source_state_id INTEGER NOT NULL,
 planning_timestamp TEXT NOT NULL, runtime_runperiod TEXT NOT NULL,
 runtime_idf_fingerprint TEXT NOT NULL, weather_fingerprint TEXT NOT NULL,
 zone_timestep_minutes INTEGER NOT NULL, tolerance_json TEXT NOT NULL,
 binding_status TEXT NOT NULL, rejection_reason TEXT, fingerprint TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS execution_effect_assessments (
 assessment_id TEXT PRIMARY KEY,
 approval_id TEXT NOT NULL REFERENCES execution_approvals(approval_id),
 native_run_id TEXT NOT NULL, shadow_run_id TEXT NOT NULL, live_run_id TEXT NOT NULL,
 assessment_json TEXT NOT NULL, effect_classification TEXT NOT NULL,
 fingerprint TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS aligned_reconciliation_points (
 reconciliation_id TEXT NOT NULL,
 approval_id TEXT NOT NULL REFERENCES execution_approvals(approval_id),
 sequence INTEGER NOT NULL, planning_timestamp TEXT NOT NULL, runtime_timestamp TEXT NOT NULL,
 timestamp_difference_seconds REAL NOT NULL, predicted_temperature REAL NOT NULL,
 simulated_temperature REAL NOT NULL, lower_bound REAL NOT NULL, upper_bound REAL NOT NULL,
 covered INTEGER NOT NULL, predicted_setpoint REAL NOT NULL, simulated_setpoint REAL NOT NULL,
 forecast_compatibility TEXT NOT NULL, occupancy_compatibility TEXT NOT NULL,
 fingerprint TEXT NOT NULL UNIQUE, PRIMARY KEY(reconciliation_id, sequence));
"""


def migrate(connection: sqlite3.Connection) -> None:
    connection.executescript(DDL)
    connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    connection.commit()
