"""Shared repository-root and recorded-demo discovery helpers."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from src.mcp_server.config import MCPSettings, load_mcp_settings

ROOT = Path(__file__).resolve().parents[1]


def mcp_settings(config: Path | None = None) -> MCPSettings:
    return load_mcp_settings((config or ROOT / "config/mcp_server.yaml").resolve())


def select_demo_run(config: Path | None = None) -> dict[str, Any]:
    settings = mcp_settings(config)
    priorities = ("module8-live-control", "module8-live-shadow", "module7-live-control")
    configured = dict(settings.runs)
    rejected: list[dict[str, str]] = []
    for run_id in priorities:
        path = configured.get(run_id)
        if path is None:
            rejected.append({"run_id": run_id, "reason": "not configured"})
            continue
        state_db, safety_db = path / "thermoledger_state.db", path / "safety_guard.db"
        if not state_db.exists():
            rejected.append({"run_id": run_id, "reason": "state database missing"})
            continue
        if run_id.startswith("module8") and not safety_db.exists():
            rejected.append({"run_id": run_id, "reason": "safety database missing"})
            continue
        connection = sqlite3.connect(f"file:{state_db.resolve()}?mode=ro", uri=True)
        try:
            latest = connection.execute(
                """SELECT sequence,environment_number FROM building_states
                ORDER BY sequence DESC LIMIT 1"""
            ).fetchone()
            historical = connection.execute(
                "SELECT sequence FROM building_states ORDER BY sequence LIMIT 1"
            ).fetchone()
            zones = {
                str(row[0])
                for row in connection.execute("SELECT DISTINCT exact_name FROM zone_states")
            }
            controller = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='control_decisions'"
            ).fetchone()[0]
        finally:
            connection.close()
        if latest is None or historical is None or not controller or "SPACE3-1" not in zones:
            rejected.append(
                {"run_id": run_id, "reason": "required state/controller/zone data missing"}
            )
            continue
        return {
            "success": True,
            "run_id": run_id,
            "environment_id": f"weather-{latest[1]}",
            "latest_state_id": int(latest[0]),
            "historical_state_id": int(historical[0]),
            "zone": "SPACE3-1",
            "space3_available": True,
            "plenum_available": "PLENUM-1" in zones,
            "state_database": str(state_db.relative_to(ROOT)),
            "safety_database": str(safety_db.relative_to(ROOT)) if safety_db.exists() else None,
            "rejected_runs": rejected,
        }
    raise RuntimeError("no usable recorded run: " + json.dumps(rejected, sort_keys=True))
