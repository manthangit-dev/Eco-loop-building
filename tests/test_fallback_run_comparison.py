import json
import sqlite3
from pathlib import Path

from scripts.compare_fallback_runs import compare


def test_comparison_reports_determinism(tmp_path: Path) -> None:
    base = tmp_path / "data/output/module_7_fallback_controller"
    for path in (
        "replay_shadow/run_1",
        "replay_shadow/run_2",
        "live_shadow/current",
        "live_control/current",
    ):
        (base / path).mkdir(parents=True)
    replay = {
        "input_state_count": 1,
        "decision_count": 5,
        "hypothetical_command_count": 5,
        "reasons": {},
        "modes": {},
        "decision_content_fingerprint": "same",
    }
    for run in ("run_1", "run_2"):
        (base / f"replay_shadow/{run}/fallback_controller_summary.json").write_text(
            json.dumps(replay)
        )
    (base / "live_shadow/current/fallback_controller_summary.json").write_text(
        json.dumps(
            {"physical_comparison_status": "PASS", "set_call_count": 0, "state_count": 35040}
        )
    )
    reference_database = (
        tmp_path / "data/output/module_6_state_bus/live/current/thermoledger_state.db"
    )
    reference_database.parent.mkdir(parents=True)
    control_database = base / "live_control/current/thermoledger_state.db"
    for database in (reference_database, control_database):
        connection = sqlite3.connect(database)
        connection.executescript(
            """CREATE TABLE building_states(
            id INTEGER,facility_purchased_electricity_raw_j REAL,hvac_electricity_raw_j REAL);
            CREATE TABLE zone_states(
            building_state_id INTEGER,zone_id TEXT,mean_air_temperature_c REAL);
            INSERT INTO building_states VALUES(1,10,5);
            INSERT INTO zone_states VALUES(1,'space3_1',24);"""
        )
        connection.close()
    (base / "live_control/current/fallback_controller_summary.json").write_text(
        json.dumps(
            {
                "set_call_count": 1,
                "reset_count": 1,
                "state_count": 35040,
                "decision_count": 35040,
                "command_count": 1,
                "expiry_count": 0,
                "rejected_count": 0,
                "database": str(control_database),
            }
        )
    )
    passed, result = compare(tmp_path)
    assert passed and result["replay_deterministic"] is True
