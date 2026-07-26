"""Additive Module 9 MCP audit schema version 4."""

import sqlite3

MCP_DATABASE_SCHEMA_VERSION = 4

SQL = """
CREATE TABLE IF NOT EXISTS mcp_tool_calls(
 tool_call_id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, tool_name TEXT NOT NULL,
 classification TEXT NOT NULL, request_json TEXT NOT NULL, response_json TEXT NOT NULL,
 success INTEGER NOT NULL, run_id TEXT, request_fingerprint TEXT NOT NULL,
 response_fingerprint TEXT NOT NULL, deterministic_order INTEGER NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS mcp_tool_errors(
 error_id TEXT PRIMARY KEY,
 tool_call_id TEXT NOT NULL REFERENCES mcp_tool_calls(tool_call_id),
 error_order INTEGER NOT NULL, code TEXT NOT NULL, message TEXT NOT NULL, field TEXT,
 UNIQUE(tool_call_id,error_order)
);
CREATE TABLE IF NOT EXISTS mcp_replay_sessions(
 replay_id TEXT PRIMARY KEY, call_count INTEGER NOT NULL, success_count INTEGER NOT NULL,
 expected_error_count INTEGER NOT NULL, physical_write_count INTEGER NOT NULL
 CHECK(physical_write_count=0),
 fingerprint TEXT NOT NULL, report_path TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_name ON mcp_tool_calls(tool_name,deterministic_order);
"""


def migrate_mcp_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("BEGIN")
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)"
        )
        row = connection.execute(
            "SELECT value FROM schema_metadata WHERE key='schema_version'"
        ).fetchone()
        version = 3 if row is None else int(row[0])
        if version > MCP_DATABASE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported future schema version {version}.")
        connection.executescript(SQL)
        connection.execute("INSERT OR REPLACE INTO schema_metadata VALUES('schema_version','4')")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
