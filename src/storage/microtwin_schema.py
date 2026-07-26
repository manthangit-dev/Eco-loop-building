"""Schema-v7 MicroTwin evidence persistence."""

# ruff: noqa: E501

import sqlite3

SQL = """
CREATE TABLE IF NOT EXISTS microtwin_models(model_id TEXT PRIMARY KEY,status TEXT NOT NULL,model_family TEXT NOT NULL,semantic_fingerprint TEXT NOT NULL UNIQUE,thermal_metrics_json TEXT NOT NULL,demand_status TEXT NOT NULL,prohibited_feature_count INTEGER NOT NULL CHECK(prohibited_feature_count=0));
CREATE TABLE IF NOT EXISTS microtwin_rollouts(rollout_id TEXT PRIMARY KEY,model_id TEXT NOT NULL REFERENCES microtwin_models(model_id),plan_id TEXT NOT NULL,context_id TEXT NOT NULL,status TEXT NOT NULL,microtwin_score REAL NOT NULL,advisory_score REAL NOT NULL,ood_feature_count INTEGER NOT NULL,physical_write_count INTEGER NOT NULL CHECK(physical_write_count=0),fingerprint TEXT NOT NULL UNIQUE,payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS microtwin_rollout_points(rollout_id TEXT NOT NULL REFERENCES microtwin_rollouts(rollout_id),timestep INTEGER NOT NULL,predicted_temperature_c REAL NOT NULL,lower_temperature_c REAL NOT NULL,upper_temperature_c REAL NOT NULL,setpoint_c REAL NOT NULL,expected_occupancy REAL NOT NULL,outdoor_temperature_c REAL NOT NULL,boundary_risk INTEGER NOT NULL,PRIMARY KEY(rollout_id,timestep));
CREATE TABLE IF NOT EXISTS microtwin_rankings(ranking_id TEXT PRIMARY KEY,model_id TEXT NOT NULL REFERENCES microtwin_models(model_id),context_id TEXT NOT NULL,selected_plan_id TEXT NOT NULL,advisory_selected_plan_id TEXT NOT NULL,agreement INTEGER NOT NULL,status TEXT NOT NULL,physical_write_count INTEGER NOT NULL CHECK(physical_write_count=0),payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS microtwin_policy_events(event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,reason_code TEXT NOT NULL,details TEXT NOT NULL);
"""


def migrate(connection: sqlite3.Connection) -> None:
    current_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(SQL)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)"
    )
    effective_version = max(current_version, 7)
    connection.execute(
        "INSERT OR REPLACE INTO schema_metadata VALUES('schema_version',?)",
        (str(effective_version),),
    )
    connection.execute(f"PRAGMA user_version={effective_version}")
    connection.commit()
