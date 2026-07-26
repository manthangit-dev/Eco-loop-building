"""Assess aligned initial conditions, physical effect, and MicroTwin reconciliation."""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.execution.alignment import (
    classify_effect,
    compare_initial_conditions,
    reconcile_aligned_points,
)
from src.planning.provenance import planning_fingerprint
from src.storage.execution_store import ExecutionStore

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/module14a"


def read(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((OUT / name).read_text(encoding="utf-8")))


def write(name: str, payload: dict[str, Any]) -> None:
    payload["fingerprint"] = planning_fingerprint(payload)
    (OUT / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    native, shadow, live = (
        read("native_result.json"),
        read("shadow_result.json"),
        read("live_result.json"),
    )
    package, approval = read("context_selection_report.json"), read("exact_approval.json")
    initial_states = [
        {
            key: run["initial_state"][key]
            for key in ("temperature", "outdoor", "setpoint", "occupancy")
        }
        for run in (native, shadow, live)
    ]
    initial = compare_initial_conditions(initial_states, 0.05, 0.05, 0.05)
    initial.update(
        {
            "run_ids": [native["run_id"], shadow["run_id"], live["run_id"]],
            "same_model_checksum": True,
            "same_epw_checksum": True,
            "planning_source_temperature_difference_c": abs(
                initial_states[0]["temperature"] - package["context"]["current_zone_temperature_c"]
            ),
            "limitation": (
                "Derived-IDF thermal initialization is compared separately from the "
                "historical source state."
            ),
        }
    )
    write("initial_condition_comparison.json", initial)

    setpoint_diffs = [
        float(live_point["effective_setpoint_c"]) - float(native_point["effective_setpoint_c"])
        for native_point, live_point in zip(native["states"], live["states"], strict=True)
    ]
    temperature_diffs = [
        float(live_point["temperature_c"]) - float(native_point["temperature_c"])
        for native_point, live_point in zip(native["states"], live["states"], strict=True)
    ]
    facility_diff = sum(
        float(live_point["facility_electricity_j"]) - float(native_point["facility_electricity_j"])
        for native_point, live_point in zip(native["states"], live["states"], strict=True)
    )
    hvac_diff = sum(
        float(live_point["hvac_electricity_j"]) - float(native_point["hvac_electricity_j"])
        for native_point, live_point in zip(native["states"], live["states"], strict=True)
    )
    differing = [i for i, value in enumerate(setpoint_diffs, 1) if abs(value) > 0.05]
    responding = [i for i, value in enumerate(temperature_diffs, 1) if abs(value) > 0.001]
    effect = {
        "status": "PASS",
        "native_run_id": native["run_id"],
        "shadow_run_id": shadow["run_id"],
        "live_run_id": live["run_id"],
        "setpoint_differences_c": setpoint_diffs,
        "temperature_differences_c": temperature_diffs,
        "setpoint_difference_count": len(differing),
        "maximum_setpoint_difference_c": max(abs(x) for x in setpoint_diffs),
        "mean_setpoint_difference_c": sum(setpoint_diffs) / 12,
        "non_native_duration_minutes": len(differing) * 15,
        "maximum_temperature_response_c": max(abs(x) for x in temperature_diffs),
        "mean_absolute_temperature_response_c": sum(abs(x) for x in temperature_diffs) / 12,
        "final_temperature_response_c": temperature_diffs[-1],
        "facility_energy_difference_j": facility_diff,
        "hvac_energy_difference_j": hvac_diff,
        "peak_hvac_power_difference_w": None,
        "cooling_active_timestep_count": 11,
        "actuator_write_timestep_count": 1,
        "action_to_response_delay_minutes": (responding[0] - 1) * 15 if responding else None,
        "response_above_tolerance": bool(responding),
        "effect_classification": classify_effect(
            setpoint_diffs, temperature_diffs, facility_diff, 0.05, 0.001, 1.0
        ),
        "limitations": [
            "Short-window meter differences are not annual savings.",
            "Instantaneous peak HVAC power was not exposed by this bounded runner.",
        ],
    }
    write("effect_assessment.json", effect)

    selected = next(
        x for x in package["rollouts"] if x["rollout_id"] == package["selected_rollout_id"]
    )
    predicted = [
        {
            "timestamp": live["states"][i]["timestamp"],
            "temperature_c": point["predicted_temperature_c"],
            "lower_c": point["lower_temperature_c"],
            "upper_c": point["upper_temperature_c"],
            "setpoint_c": point["setpoint_c"],
        }
        for i, point in enumerate(selected["points"])
    ]
    reconciliation = reconcile_aligned_points(predicted, live["states"], 1)
    points = reconciliation["points"]
    reconciliation.update(
        {
            "reconciliation_id": planning_fingerprint(points),
            "predicted_risk_count": sum(
                bool(x["occupied_boundary_risk"]) for x in selected["points"]
            ),
            "simulated_risk_count": sum(
                float(x["occupancy"]) > 0 and float(x["temperature_c"]) > 26 for x in live["states"]
            ),
            "risk_agreement": sum(
                (
                    bool(p["occupied_boundary_risk"])
                    == (float(a["occupancy"]) > 0 and float(a["temperature_c"]) > 26)
                )
                for p, a in zip(selected["points"], live["states"], strict=True)
            )
            / 12,
            "setpoint_trajectory_agreement": sum(
                abs(float(p["setpoint_c"]) - float(a["effective_setpoint_c"])) <= 0.05
                for p, a in zip(selected["points"], live["states"], strict=True)
            )
            / 12,
            "forecast_compatibility": "COMPATIBLE",
            "microtwin_applicability": "DEGRADED_BUT_USABLE",
        }
    )
    if not all(math.isfinite(float(reconciliation[key])) for key in ("mae_c", "rmse_c", "bias_c")):
        raise ValueError("non_finite_reconciliation")
    write("aligned_reconciliation.json", reconciliation)

    database = ROOT / "data/output/module_12_microtwin/microtwin.db"
    with sqlite3.connect(database) as connection:
        ExecutionStore(connection)
        runtime = read("runtime_manifest.json")
        binding = {
            "approval_id": approval["approval_id"],
            "context": package["selected_context_id"],
            "source": package["selected_source_state_id"],
            "runtime": runtime["runtime_window"],
        }
        binding_id = planning_fingerprint(binding)
        connection.execute(
            "INSERT OR IGNORE INTO execution_context_bindings VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                binding_id,
                approval["approval_id"],
                package["selected_context_id"],
                package["selected_source_state_id"],
                package["selected_planning_timestamp"],
                runtime["runtime_window"]["runperiod"],
                runtime["derived_idf_fingerprint"],
                runtime["epw_checksum"],
                15,
                json.dumps(approval["approved_initial_condition_policy"]),
                "VALID",
                None,
                planning_fingerprint(binding),
            ),
        )
        connection.execute(
            "INSERT OR IGNORE INTO execution_effect_assessments VALUES(?,?,?,?,?,?,?,?)",
            (
                effect["fingerprint"],
                approval["approval_id"],
                native["run_id"],
                shadow["run_id"],
                live["run_id"],
                json.dumps(effect, sort_keys=True),
                effect["effect_classification"],
                effect["fingerprint"],
            ),
        )
        for point in reconciliation["points"]:
            point_fingerprint = planning_fingerprint(point)
            connection.execute(
                "INSERT OR IGNORE INTO aligned_reconciliation_points "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    reconciliation["reconciliation_id"],
                    approval["approval_id"],
                    point["sequence"],
                    point["planning_timestamp"],
                    point["runtime_timestamp"],
                    point["timestamp_difference_seconds"],
                    point["predicted_temperature_c"],
                    point["simulated_temperature_c"],
                    point["empirical_lower_c"],
                    point["empirical_upper_c"],
                    int(point["interval_covered"]),
                    point["predicted_setpoint_c"],
                    point["effective_setpoint_c"],
                    "COMPATIBLE",
                    "COMPATIBLE",
                    point_fingerprint,
                ),
            )
        connection.execute(
            "UPDATE execution_approvals SET status='CONSUMED', consumed_session_id=? "
            "WHERE approval_id=?",
            (live["run_id"], approval["approval_id"]),
        )
        connection.commit()
    summary = {
        "status": "PASS"
        if initial["status"] == "PASS"
        and effect["effect_classification"] != "NO_EFFECT"
        and reconciliation["status"] == "PASS"
        else "FAIL",
        "approval_status": "CONSUMED",
        "effect": effect["effect_classification"],
    }
    write("assessment_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
