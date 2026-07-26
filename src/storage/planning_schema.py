"""Additive schema-v6 planning database."""
# ruff: noqa: E501

import sqlite3

SCHEMA_VERSION = 6
SQL = """
CREATE TABLE IF NOT EXISTS planning_contexts(context_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,environment_id TEXT NOT NULL,source_state_id INTEGER NOT NULL,planning_timestamp TEXT NOT NULL,target_zone TEXT NOT NULL,actuator_identity TEXT NOT NULL,horizon INTEGER NOT NULL,context_fingerprint TEXT NOT NULL UNIQUE,prohibited_future_source_count INTEGER NOT NULL CHECK(prohibited_future_source_count=0),uncertainty TEXT NOT NULL,schema_version INTEGER NOT NULL,payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS planning_forecast_points(context_id TEXT NOT NULL REFERENCES planning_contexts(context_id),forecast_type TEXT NOT NULL,sequence INTEGER NOT NULL,simulation_timestamp TEXT NOT NULL,zone TEXT,value REAL NOT NULL,units TEXT NOT NULL,uncertainty TEXT NOT NULL,source TEXT NOT NULL,provenance_fingerprint TEXT NOT NULL,PRIMARY KEY(context_id,forecast_type,sequence));
CREATE TABLE IF NOT EXISTS candidate_plans(plan_id TEXT PRIMARY KEY,context_id TEXT NOT NULL REFERENCES planning_contexts(context_id),strategy_type TEXT NOT NULL,status TEXT NOT NULL,advisory_score REAL NOT NULL,first_action_guard_outcome TEXT NOT NULL,first_action_guard_reason TEXT NOT NULL,fingerprint TEXT NOT NULL UNIQUE,schema_version INTEGER NOT NULL,payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS candidate_actions(plan_id TEXT NOT NULL REFERENCES candidate_plans(plan_id),action_sequence INTEGER NOT NULL,timestep_offset INTEGER NOT NULL,intended_timestamp TEXT NOT NULL,actuator_identity TEXT NOT NULL,requested_value REAL NOT NULL,units TEXT NOT NULL,action_type TEXT NOT NULL,rationale_code TEXT NOT NULL,execution_time_guard_required INTEGER NOT NULL,PRIMARY KEY(plan_id,action_sequence));
CREATE TABLE IF NOT EXISTS plan_score_components(plan_id TEXT NOT NULL REFERENCES candidate_plans(plan_id),component TEXT NOT NULL,raw_value REAL NOT NULL,weight REAL NOT NULL,weighted_value REAL NOT NULL,explanation_code TEXT NOT NULL,PRIMARY KEY(plan_id,component));
CREATE TABLE IF NOT EXISTS plan_validation_events(plan_id TEXT NOT NULL REFERENCES candidate_plans(plan_id),sequence INTEGER NOT NULL,severity TEXT NOT NULL,reason_code TEXT NOT NULL,details TEXT NOT NULL,PRIMARY KEY(plan_id,sequence));
CREATE TABLE IF NOT EXISTS planning_sessions(session_id TEXT PRIMARY KEY,context_id TEXT NOT NULL REFERENCES planning_contexts(context_id),deterministic_selected_plan TEXT REFERENCES candidate_plans(plan_id),llm_recommended_plan TEXT REFERENCES candidate_plans(plan_id),agreement_status TEXT NOT NULL,status TEXT NOT NULL,physical_write_performed INTEGER NOT NULL CHECK(physical_write_performed=0),provider TEXT NOT NULL,model TEXT NOT NULL,fingerprint TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plan_selections(selection_id TEXT PRIMARY KEY,planning_session_id TEXT NOT NULL REFERENCES planning_sessions(session_id),selected_plan_id TEXT NOT NULL REFERENCES candidate_plans(plan_id),selection_mode TEXT NOT NULL,evidence_validation_result TEXT NOT NULL,advisory_only INTEGER NOT NULL CHECK(advisory_only=1));
"""


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(SQL)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)"
    )
    connection.execute("INSERT OR REPLACE INTO schema_metadata VALUES('schema_version','6')")
    connection.commit()
