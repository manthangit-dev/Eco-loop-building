"""Additive schema-v8 Comfort Ledger and Thermal Bank persistence."""

# ruff: noqa: E501

from __future__ import annotations

import sqlite3

SQL = """
CREATE TABLE IF NOT EXISTS comfort_ledger_accounts(account_id TEXT PRIMARY KEY,zone TEXT NOT NULL,schema_version INTEGER NOT NULL,status TEXT NOT NULL,opening_sequence INTEGER NOT NULL,current_credit REAL NOT NULL CHECK(current_credit>=0),current_debt REAL NOT NULL CHECK(current_debt>=0),current_debt_status TEXT NOT NULL,fingerprint TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS comfort_ledger_entries(entry_id TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES comfort_ledger_accounts(account_id),context_id TEXT NOT NULL,plan_id TEXT NOT NULL,rollout_id TEXT NOT NULL REFERENCES microtwin_rollouts(rollout_id),event_id TEXT,timestep INTEGER NOT NULL,simulation_timestamp TEXT NOT NULL,entry_type TEXT NOT NULL,evidence_type TEXT NOT NULL,occupancy REAL NOT NULL,lower_boundary REAL NOT NULL,upper_boundary REAL NOT NULL,predicted_temperature REAL NOT NULL,lower_uncertainty REAL NOT NULL,upper_uncertainty REAL NOT NULL,burden REAL NOT NULL CHECK(burden>=0),credit REAL NOT NULL CHECK(credit>=0),debt REAL NOT NULL CHECK(debt>=0),repayment REAL NOT NULL CHECK(repayment>=0),reason_code TEXT NOT NULL,fingerprint TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS comfort_debt_records(debt_id TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES comfort_ledger_accounts(account_id),source_entry TEXT NOT NULL REFERENCES comfort_ledger_entries(entry_id),initial_debt REAL NOT NULL CHECK(initial_debt>=0),remaining_debt REAL NOT NULL CHECK(remaining_debt>=0),creation_timestamp TEXT NOT NULL,age INTEGER NOT NULL CHECK(age>=0),status TEXT NOT NULL,recovery_requirement REAL NOT NULL CHECK(recovery_requirement>=0),closure_timestamp TEXT);
CREATE TABLE IF NOT EXISTS comfort_debt_repayments(repayment_id TEXT PRIMARY KEY,debt_id TEXT NOT NULL REFERENCES comfort_debt_records(debt_id),source_plan TEXT NOT NULL,source_entry TEXT NOT NULL REFERENCES comfort_ledger_entries(entry_id),amount REAL NOT NULL CHECK(amount>=0),timestamp TEXT NOT NULL,reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS comfort_fairness_assessments(assessment_id TEXT PRIMARY KEY,context_id TEXT NOT NULL,plan_id TEXT NOT NULL,event_metrics TEXT NOT NULL,temporal_metrics TEXT NOT NULL,equity_score REAL NOT NULL CHECK(equity_score>=0 AND equity_score<=100),threshold_status TEXT NOT NULL,reason_codes TEXT NOT NULL,fingerprint TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS thermal_bank_accounts(account_id TEXT PRIMARY KEY,zone TEXT NOT NULL,unit TEXT NOT NULL CHECK(unit='RTFU'),status TEXT NOT NULL,opening_sequence INTEGER NOT NULL,current_balance REAL NOT NULL CHECK(current_balance>=0),schema_version INTEGER NOT NULL,fingerprint TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS thermal_bank_transactions(transaction_id TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES thermal_bank_accounts(account_id),sequence INTEGER NOT NULL,timestamp TEXT NOT NULL,transaction_type TEXT NOT NULL,amount REAL NOT NULL CHECK(amount>=0),opening_balance REAL NOT NULL CHECK(opening_balance>=0),closing_balance REAL NOT NULL CHECK(closing_balance>=0),source_plan TEXT NOT NULL,source_rollout TEXT NOT NULL REFERENCES microtwin_rollouts(rollout_id),source_event TEXT,expiry_timestamp TEXT,reason_code TEXT NOT NULL,fingerprint TEXT NOT NULL UNIQUE,UNIQUE(account_id,sequence));
CREATE TABLE IF NOT EXISTS ledger_plan_evaluations(evaluation_id TEXT PRIMARY KEY,context_id TEXT NOT NULL,plan_id TEXT NOT NULL,rollout_id TEXT NOT NULL REFERENCES microtwin_rollouts(rollout_id),comfort_burden REAL NOT NULL CHECK(comfort_burden>=0),comfort_credit REAL NOT NULL CHECK(comfort_credit>=0),opening_debt REAL NOT NULL CHECK(opening_debt>=0),closing_debt REAL NOT NULL CHECK(closing_debt>=0),equity_score REAL NOT NULL CHECK(equity_score>=0 AND equity_score<=100),opening_bank_balance REAL NOT NULL CHECK(opening_bank_balance>=0),deposit REAL NOT NULL CHECK(deposit>=0),withdrawal REAL NOT NULL CHECK(withdrawal>=0),reserves REAL NOT NULL CHECK(reserves>=0),closing_bank_balance REAL NOT NULL CHECK(closing_bank_balance>=0),advisory_score REAL NOT NULL,microtwin_score REAL NOT NULL,ledger_aware_score REAL NOT NULL,eligibility INTEGER NOT NULL,rejection_reasons TEXT NOT NULL,physical_write_performed INTEGER NOT NULL CHECK(physical_write_performed=0),fingerprint TEXT NOT NULL UNIQUE,payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger_rankings(ranking_id TEXT PRIMARY KEY,context_id TEXT NOT NULL,ranked_plan_ids TEXT NOT NULL,module11_ranking TEXT NOT NULL,module12_ranking TEXT NOT NULL,module13_ranking TEXT NOT NULL,agreement_status INTEGER NOT NULL,selected_plan TEXT NOT NULL,physical_write_performed INTEGER NOT NULL CHECK(physical_write_performed=0),fingerprint TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS ledger_sessions(session_id TEXT PRIMARY KEY,context_id TEXT NOT NULL,deterministic_selected_plan TEXT NOT NULL,llm_recommended_plan TEXT,agreement INTEGER,evidence_validation INTEGER NOT NULL,provider TEXT NOT NULL,model TEXT NOT NULL,physical_write_performed INTEGER NOT NULL CHECK(physical_write_performed=0),fingerprint TEXT NOT NULL UNIQUE);
"""


def migrate(connection: sqlite3.Connection) -> None:
    current_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(SQL)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)"
    )
    effective_version = max(current_version, 8)
    connection.execute(
        "INSERT OR REPLACE INTO schema_metadata VALUES('schema_version',?)",
        (str(effective_version),),
    )
    connection.execute(f"PRAGMA user_version={effective_version}")
    connection.commit()
