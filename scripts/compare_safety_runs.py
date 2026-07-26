"""Compare Module 7 and Module 8 guarded live-control evidence."""

import json
import sqlite3
from pathlib import Path


def diagnostics(path: Path) -> tuple[float, float, float]:
    connection = sqlite3.connect(path)
    row = connection.execute("""SELECT AVG(z.mean_air_temperature_c),
        AVG(b.facility_purchased_electricity_raw_j),AVG(b.hvac_electricity_raw_j)
        FROM zone_states z JOIN building_states b ON b.id=z.building_state_id
        WHERE z.zone_id='space3_1'""").fetchone()
    connection.close()
    return float(row[0]), float(row[1]), float(row[2])


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    m7 = root / "data/output/module_7_fallback_controller/live_control/current"
    m8 = root / "data/output/module_8_safety_guard/live_control/current"
    seven = json.loads((m7 / "fallback_controller_summary.json").read_text())
    eight = json.loads((m8 / "fallback_controller_summary.json").read_text())
    d7, d8 = diagnostics(m7 / "thermoledger_state.db"), diagnostics(m8 / "thermoledger_state.db")
    transparent = all(
        seven[key] == eight[key]
        for key in (
            "state_count",
            "decision_count",
            "command_count",
            "set_call_count",
            "reset_count",
            "decisions_by_mode",
            "decisions_by_reason",
            "effective_setpoint_response",
        )
    )
    report = {
        "status": "PASS" if transparent else "FAIL",
        "transparent": transparent,
        "effective_setpoint_comparison": "IDENTICAL"
        if seven["effective_setpoint_response"] == eight["effective_setpoint_response"]
        else "DIFFERENT",
        "target_temperature_difference_module8_minus_module7_c": d8[0] - d7[0],
        "facility_electricity_difference_module8_minus_module7_j_per_timestep": d8[1] - d7[1],
        "hvac_electricity_difference_module8_minus_module7_j_per_timestep": d8[2] - d7[2],
        "interpretation": "diagnostic parity only; not an energy-saving claim",
    }
    path = root / "data/output/module_8_safety_guard/module7_vs_module8_comparison.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if transparent else 1


if __name__ == "__main__":
    raise SystemExit(main())
