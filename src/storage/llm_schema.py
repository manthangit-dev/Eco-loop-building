"""Additive Module 10 schema-v5 LLM audit migration."""

import sqlite3

LLM_DATABASE_SCHEMA_VERSION = 5

SQL = """
CREATE TABLE IF NOT EXISTS llm_sessions(
 session_id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, objective_type TEXT NOT NULL,
 provider TEXT NOT NULL, model TEXT NOT NULL, status TEXT NOT NULL, run_id TEXT NOT NULL,
 tool_catalogue_fingerprint TEXT NOT NULL, prompt_template_version INTEGER NOT NULL,
 schema_version INTEGER NOT NULL, deterministic_mock INTEGER NOT NULL,
 physical_write_performed INTEGER NOT NULL CHECK(physical_write_performed=0),
 iteration_count INTEGER NOT NULL, tool_call_count INTEGER NOT NULL,
 correction_count INTEGER NOT NULL, input_token_estimate INTEGER NOT NULL,
 output_token_estimate INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS llm_messages(
 session_id TEXT NOT NULL REFERENCES llm_sessions(session_id), sequence INTEGER NOT NULL,
 role TEXT NOT NULL, message_type TEXT NOT NULL, content TEXT NOT NULL,
 content_fingerprint TEXT NOT NULL, included_in_final_context INTEGER NOT NULL,
 PRIMARY KEY(session_id,sequence)
);
CREATE TABLE IF NOT EXISTS llm_tool_steps(
 session_id TEXT NOT NULL REFERENCES llm_sessions(session_id), sequence INTEGER NOT NULL,
 mcp_tool_call_id TEXT NOT NULL, selected_tool TEXT NOT NULL, canonical_arguments TEXT NOT NULL,
 result_fingerprint TEXT NOT NULL, success INTEGER NOT NULL, error_code TEXT,
 reused_response INTEGER NOT NULL, PRIMARY KEY(session_id,sequence)
);
CREATE TABLE IF NOT EXISTS llm_policy_events(
 session_id TEXT NOT NULL REFERENCES llm_sessions(session_id), sequence INTEGER NOT NULL,
 event_type TEXT NOT NULL, reason_code TEXT NOT NULL, attempted_tool TEXT, details TEXT NOT NULL,
 PRIMARY KEY(session_id,sequence)
);
CREATE TABLE IF NOT EXISTS llm_final_responses(
 session_id TEXT PRIMARY KEY REFERENCES llm_sessions(session_id), response_json TEXT NOT NULL,
 response_fingerprint TEXT NOT NULL, evidence_validation_result TEXT NOT NULL,
 physical_write_performed INTEGER NOT NULL CHECK(physical_write_performed=0)
);
CREATE TABLE IF NOT EXISTS llm_provider_events(
 event_id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT REFERENCES llm_sessions(session_id),
 event_type TEXT NOT NULL, details TEXT NOT NULL
);
"""


def migrate_llm_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("BEGIN")
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)"
        )
        row = connection.execute(
            "SELECT value FROM schema_metadata WHERE key='schema_version'"
        ).fetchone()
        version = 4 if row is None else int(row[0])
        if version > LLM_DATABASE_SCHEMA_VERSION:
            raise ValueError("database schema is newer than Module 10")
        connection.executescript(SQL)
        connection.execute(
            "INSERT OR REPLACE INTO schema_metadata VALUES('schema_version',?)",
            (str(LLM_DATABASE_SCHEMA_VERSION),),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
