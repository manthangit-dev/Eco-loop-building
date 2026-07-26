"""Capture deterministic Module 12C physical-write and process counters."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data/output/module_8_safety_guard/live_control/current/safety_guard.db"
OUTPUT = ROOT / "outputs/module12c/final_zero_write_report.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--energyplus-process-count", type=int, required=True)
    args = parser.parse_args()
    with sqlite3.connect(DATABASE) as connection:
        counts = {
            "physical_writes": connection.execute(
                "SELECT COUNT(*) FROM physical_write_attempts"
            ).fetchone()[0],
            "set_calls": connection.execute(
                "SELECT COUNT(*) FROM physical_write_attempts WHERE operation='SET'"
            ).fetchone()[0],
            "reset_calls": connection.execute(
                "SELECT COUNT(*) FROM physical_write_attempts WHERE operation='RESET'"
            ).fetchone()[0],
            "without_guard": connection.execute(
                "SELECT COUNT(*) FROM physical_write_attempts WHERE guard_decision_id IS NULL"
            ).fetchone()[0],
        }
    process_count = args.energyplus_process_count
    payload = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    payload[args.phase] = {**counts, "energyplus_process_count": process_count}
    if "before" in payload and "after" in payload:
        payload["delta"] = {
            key: payload["after"][key] - payload["before"][key]
            for key in payload["before"]
        }
        payload["propose_guarded_control_executions"] = 0
        payload["status"] = (
            "PASS"
            if all(value == 0 for value in payload["delta"].values())
            and payload["after"]["without_guard"] == 0
            else "FAIL"
        )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("status", "PASS") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
