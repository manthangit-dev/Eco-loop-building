"""Compare Module 7 deterministic replay and live run summaries."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path


def compare(root: Path) -> tuple[bool, dict[str, object]]:
    base = root / "data/output/module_7_fallback_controller"
    first = json.loads((base / "replay_shadow/run_1/fallback_controller_summary.json").read_text())
    second = json.loads((base / "replay_shadow/run_2/fallback_controller_summary.json").read_text())
    shadow = json.loads((base / "live_shadow/current/fallback_controller_summary.json").read_text())
    control = json.loads(
        (base / "live_control/current/fallback_controller_summary.json").read_text()
    )

    def diagnostics(path: Path) -> tuple[float, float, float]:
        connection = sqlite3.connect(path)
        values = connection.execute(
            """SELECT AVG(z.mean_air_temperature_c),
                      AVG(b.facility_purchased_electricity_raw_j),
                      AVG(b.hvac_electricity_raw_j)
               FROM zone_states z JOIN building_states b ON b.id=z.building_state_id
               WHERE z.zone_id='space3_1'"""
        ).fetchone()
        connection.close()
        return float(values[0]), float(values[1]), float(values[2])

    reference_values = diagnostics(
        root / "data/output/module_6_state_bus/live/current/thermoledger_state.db"
    )
    control_values = diagnostics(Path(control["database"]))
    deterministic = all(
        first[key] == second[key]
        for key in (
            "input_state_count",
            "decision_count",
            "hypothetical_command_count",
            "reasons",
            "modes",
            "decision_content_fingerprint",
        )
    )
    passed = (
        deterministic
        and shadow["physical_comparison_status"] == "PASS"
        and shadow["set_call_count"] == 0
        and control["set_call_count"] > 0
        and control["reset_count"] > 0
    )
    payload: dict[str, object] = {
        "status": "PASS" if passed else "FAIL",
        "replay_deterministic": deterministic,
        "shadow_physical_parity": shadow["physical_comparison_status"],
        "reference_state_count": 35040,
        "shadow_state_count": shadow["state_count"],
        "control_state_count": control["state_count"],
        "control_decision_count": control["decision_count"],
        "real_command_count": control["command_count"],
        "set_call_count": control["set_call_count"],
        "reset_count": control["reset_count"],
        "command_expiry_count": control["expiry_count"],
        "rejected_decision_count": control["rejected_count"],
        "electricity_label": "experimental fallback-control difference; not energy savings",
        "target_temperature_diagnostic_difference_c": control_values[0] - reference_values[0],
        "facility_electricity_diagnostic_difference_j_per_timestep": (
            control_values[1] - reference_values[1]
        ),
        "hvac_electricity_diagnostic_difference_j_per_timestep": (
            control_values[2] - reference_values[2]
        ),
        "safety_guard_status": "not_implemented_module_8_pending",
    }
    path = base / "fallback_run_comparison.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return passed, payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    passed, payload = compare(root)
    print(json.dumps(payload, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
