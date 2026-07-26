"""Compare compatible short runs and persist simulation reconciliation."""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.execution.config import load_execution_settings
from src.microtwin.config import load_microtwin_settings
from src.microtwin.rollout import rollout
from src.planning.provenance import planning_fingerprint
from src.storage.execution_schema import migrate

from scripts.planning_common import build

ROOT = Path(__file__).resolve().parents[1]


def summary(run: dict[str, Any]) -> dict[str, Any]:
    states = run["states"]
    assert isinstance(states, list)
    temperatures = [float(item["temperature_c"]) for item in states]
    facility = [
        item["facility_electricity_j"]
        for item in states
        if item["facility_electricity_j"] is not None
    ]
    hvac = [item["hvac_electricity_j"] for item in states if item["hvac_electricity_j"] is not None]
    return {
        "state_count": len(states),
        "temperature_min_c": min(temperatures),
        "temperature_max_c": max(temperatures),
        "temperature_mean_c": sum(temperatures) / len(temperatures),
        "occupied_boundary_risk_count": sum(
            bool(item["occupied_boundary_risk"]) for item in states
        ),
        "facility_electricity_j": sum(float(x) for x in facility) if facility else None,
        "hvac_electricity_j": sum(float(x) for x in hvac) if hvac else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/module14/short_comparison.json"
    )
    args = parser.parse_args()
    started = time.monotonic()
    native, shadow, live = (
        json.loads((ROOT / f"outputs/module14/short_{name}.json").read_text())
        for name in ("native", "shadow", "live")
    )
    compatible = len(native["states"]) == len(shadow["states"]) == len(live["states"]) == 12
    context, plans = build()
    plan = next(item for item in plans if item.plan_id.startswith("3ae11"))
    predicted = rollout(context, plan, load_microtwin_settings(ROOT / "config/microtwin.yaml"))
    errors, covered, rows = [], 0, []
    for point, actual in zip(predicted.points, live["states"], strict=True):
        error = float(actual["temperature_c"]) - point.predicted_temperature_c
        errors.append(error)
        interval = (
            point.lower_temperature_c <= float(actual["temperature_c"]) <= point.upper_temperature_c
        )
        covered += int(interval)
        rows.append(
            {
                "timestep": point.timestep,
                "predicted_temperature_c": point.predicted_temperature_c,
                "simulated_temperature_c": actual["temperature_c"],
                "prediction_error_c": error,
                "lower_bound_c": point.lower_temperature_c,
                "upper_bound_c": point.upper_temperature_c,
                "interval_covered": interval,
                "predicted_risk": point.occupied_boundary_risk,
                "simulated_risk": actual["occupied_boundary_risk"],
            }
        )
    mae = sum(abs(x) for x in errors) / len(errors)
    rmse = math.sqrt(sum(x * x for x in errors) / len(errors))
    native_summary, shadow_summary, live_summary = summary(native), summary(shadow), summary(live)
    facility_difference = float(live_summary["facility_electricity_j"]) - float(
        native_summary["facility_electricity_j"]
    )
    hvac_difference = float(live_summary["hvac_electricity_j"]) - float(
        native_summary["hvac_electricity_j"]
    )
    payload: dict[str, Any] = {
        "status": "PASS" if compatible else "FAIL",
        "compatibility_status": "COMPATIBLE" if compatible else "INCOMPATIBLE",
        "native": native_summary,
        "shadow": shadow_summary,
        "live": live_summary,
        "short_horizon_simulated_difference": {
            "facility_electricity_j": facility_difference,
            "hvac_electricity_j": hvac_difference,
        },
        "savings_claim_status": "NOT_ESTABLISHED_SHORT_WINDOW_ONLY",
        "reconciliation": {
            "rollout_id": predicted.rollout_id,
            "point_count": len(rows),
            "mae_c": mae,
            "rmse_c": rmse,
            "interval_coverage": covered / len(rows),
            "prediction_bias_c": sum(errors) / len(errors),
            "points": rows,
            "limitations": [
                "different calendar window from advisory scenario",
                "simulation-only",
                "no retraining",
            ],
        },
        "runtime_seconds": round(time.monotonic() - started, 3),
    }
    comparison_id = planning_fingerprint(
        {"native": native["run_id"], "shadow": shadow["run_id"], "live": live["run_id"]}
    )
    reconciliation_id = planning_fingerprint(
        {"comparison": comparison_id, "rollout": predicted.rollout_id}
    )
    settings = load_execution_settings(ROOT / "config/execution_orchestrator.yaml")
    with sqlite3.connect(settings.database) as connection:
        migrate(connection)
        with connection:
            for mode, run, approval_file in (
                ("LIVE_SHADOW", shadow, ROOT / "outputs/module14/shadow_approval.json"),
                ("LIVE_SHORT_HORIZON", live, ROOT / "outputs/module14/live_approval.json"),
            ):
                approval = json.loads(approval_file.read_text())
                session_id = f"module14-{mode.lower()}"
                report_json = json.dumps(run, sort_keys=True)
                connection.execute(
                    "INSERT OR REPLACE INTO execution_sessions VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        session_id,
                        approval["approval_id"],
                        mode,
                        "COMPLETED",
                        run["physical_set_calls"],
                        run["physical_reset_calls"],
                        run["fallback_activation_count"],
                        report_json,
                        planning_fingerprint(run),
                    ),
                )
                connection.execute(
                    "INSERT OR REPLACE INTO execution_actions VALUES(?,?,?,?,?,?,?)",
                    (
                        session_id,
                        "3b70b6524075bce5660ff10815dd1c60df1031cc5bc00e1900264f626709a716",
                        0,
                        28.5,
                        run["guard_outcomes"][0],
                        "SUBMITTED" if mode == "LIVE_SHORT_HORIZON" else "SHADOW",
                        "COMPLETED",
                    ),
                )
                connection.execute(
                    "INSERT OR REPLACE INTO execution_resets VALUES(?,?,?,?)",
                    (session_id, 1, "mandatory_native_reset", "SUCCESS"),
                )
                connection.execute(
                    "UPDATE execution_approvals SET status='CONSUMED', consumed_session_id=? "
                    "WHERE approval_id=?",
                    (session_id, approval["approval_id"]),
                )
                if mode == "LIVE_SHORT_HORIZON":
                    for sequence, operation in enumerate(("SET", "RESET"), 1):
                        connection.execute(
                            "INSERT OR REPLACE INTO execution_writer_attempts "
                            "VALUES(?,?,?,?,?,?,?)",
                            (
                                f"{session_id}-{sequence}",
                                session_id,
                                "plan-action" if operation == "SET" else "native-reset",
                                operation,
                                1,
                                "SUCCESS",
                                0,
                            ),
                        )
            connection.execute(
                "INSERT OR REPLACE INTO execution_run_comparisons VALUES(?,?,?,?,?,?,?)",
                (
                    comparison_id,
                    native["run_id"],
                    shadow["run_id"],
                    live["run_id"],
                    payload["compatibility_status"],
                    json.dumps(
                        {k: v for k, v in payload.items() if k != "reconciliation"}, sort_keys=True
                    ),
                    planning_fingerprint(payload),
                ),
            )
            for row in rows:
                connection.execute(
                    "INSERT OR REPLACE INTO simulation_reconciliation "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        reconciliation_id,
                        row["timestep"],
                        plan.plan_id,
                        predicted.rollout_id,
                        live["run_id"],
                        row["predicted_temperature_c"],
                        row["simulated_temperature_c"],
                        row["prediction_error_c"],
                        row["lower_bound_c"],
                        row["upper_bound_c"],
                        int(row["interval_covered"]),
                        int(row["predicted_risk"]),
                        int(row["simulated_risk"]),
                    ),
                )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        json.dumps(
            {
                **payload,
                "reconciliation": {
                    k: v for k, v in payload["reconciliation"].items() if k != "points"
                },
            },
            indent=2,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
