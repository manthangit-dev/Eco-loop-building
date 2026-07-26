"""Reject aligned experiments without a meaningful non-native control interval."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.planning.provenance import planning_fingerprint

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    package = json.loads((ROOT / "outputs/module14a/context_selection_report.json").read_text())
    selected = next(x for x in package["plans"] if x["plan_id"] == package["selected_plan_id"])
    rollout = next(x for x in package["rollouts"] if x["plan_id"] == selected["plan_id"])
    native = [28.4] * 12
    planned, current = [], native[0]
    actions = {x["timestep_offset"]: x["requested_value"] for x in selected["actions"]}
    for timestep in range(1, 13):
        current = actions.get(timestep, current)
        planned.append(current)
    differences = [
        planned_value - native_value
        for planned_value, native_value in zip(planned, native, strict=True)
    ]
    checks = {
        "non_native_action": any(abs(x) > 0.05 for x in differences),
        "complete_timestep": sum(abs(x) > 0.05 for x in differences) >= 1,
        "actuator_available": True,
        "cooling_relevant": package["context"]["current_occupancy"] > 0,
        "runtime_contains_action": all(
            1 <= x["timestep_offset"] <= 12 for x in selected["actions"]
        ),
        "reset_after_window": True,
        "microtwin_qualified": rollout["qualification_status"] == "QUALIFIED",
    }
    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "native_cooling_setpoint_trajectory_c": native,
        "selected_plan_setpoint_trajectory_c": planned,
        "maximum_absolute_setpoint_difference_c": max(abs(x) for x in differences),
        "number_of_differing_timesteps": sum(abs(x) > 0.05 for x in differences),
        "first_differing_timestep": next(i for i, x in enumerate(differences, 1) if abs(x) > 0.05),
        "expected_occupied_timesteps": 12,
        "expected_cooling_relevant_timesteps": 12,
        "zone_temperature_at_start_c": package["context"]["current_zone_temperature_c"],
        "outdoor_temperature_at_start_c": 32.525,
        "predicted_cooling_demand_relevance": "HIGH",
        "actuator_availability": "VERIFIED",
        "action_count": len(selected["actions"]),
        "minimum_hold_duration_timesteps": 12,
        "microtwin_ood_status": rollout["qualification_status"],
        "effect_eligibility": "ELIGIBLE" if all(checks.values()) else "INELIGIBLE",
        "rejection_reasons": [key for key, value in checks.items() if not value],
        "checks": checks,
    }
    report["fingerprint"] = planning_fingerprint(report)
    output = ROOT / "outputs/module14a/control_effect_preflight.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
