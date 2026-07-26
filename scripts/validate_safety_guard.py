"""Validate completed Module 8 artifacts without rerunning EnergyPlus."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    base = root / "data/output/module_8_safety_guard"
    shadow = json.loads((base / "live_shadow/current/fallback_controller_summary.json").read_text())
    live = json.loads((base / "live_control/current/fallback_controller_summary.json").read_text())
    challenge = json.loads((base / "challenges/run_1/safety_challenge_report.json").read_text())
    replay = json.loads((base / "replay/run_1/safety_replay_report.json").read_text())
    connection = sqlite3.connect(base / "live_control/current/safety_guard.db")
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign = len(connection.execute("PRAGMA foreign_key_check").fetchall())
    writes = int(
        connection.execute(
            "SELECT COUNT(*) FROM physical_write_attempts WHERE permitted=1"
        ).fetchone()[0]
    )
    unguarded = int(
        connection.execute(
            "SELECT COUNT(*) FROM physical_write_attempts WHERE guard_decision_id IS NULL"
        ).fetchone()[0]
    )
    outcomes = {
        str(row[0]): int(row[1])
        for row in connection.execute(
            "SELECT outcome,COUNT(*) FROM safety_guard_decisions GROUP BY outcome"
        )
    }
    connection.close()
    checks = {
        "challenge_50_pass": challenge["case_count"] == challenge["passed_count"] == 50,
        "replay_complete": replay["guard_decision_count"] == 35040,
        "shadow_complete": shadow["guard_decision_count"] == 175200,
        "shadow_zero_writes": shadow["set_call_count"] == shadow["reset_count"] == 0,
        "shadow_parity": shadow["physical_comparison_status"] == "PASS",
        "live_complete": live["guard_decision_count"] == 35041,
        "live_guarded_writes": writes == live["set_call_count"] + live["reset_count"],
        "zero_unguarded": unguarded == 0,
        "zero_errors": all(
            live[key] == 0
            for key in (
                "api_error_count",
                "callback_error_count",
                "subscriber_error_count",
                "persistence_error_count",
                "guard_internal_error_count",
                "guard_persistence_error_count",
            )
        ),
        "energyplus_clean": live["energyplus_exit_code"]
        == live["warning_count"]
        == live["severe_count"]
        == live["fatal_count"]
        == 0,
        "integrity": integrity == "ok",
        "foreign_keys": foreign == 0,
        "one_actuator": live["actuator_identity_count"] == 1,
        "zero_plenum_future_bounds": live["plenum_action_count"]
        == live["future_state_use_count"]
        == live["out_of_bounds_action_count"]
        == 0,
    }
    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "physical_write_attempt_count": writes,
        "unguarded_write_count": unguarded,
        "guard_outcomes": outcomes,
        "integrity_check": integrity,
        "foreign_key_violations": foreign,
    }
    path = base / "safety_guard_validation_summary.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
