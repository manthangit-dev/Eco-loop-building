"""Safe predefined read-only database queries."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def open_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = (
        "simulation_runs",
        "building_states",
        "zone_states",
        "sensor_availability",
        "state_quality_issues",
        "storage_events",
    )
    return {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }


def rows_as_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]
