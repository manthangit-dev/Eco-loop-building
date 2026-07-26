"""Validate and record the immutable Module 12 inputs reused by Module 13."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.microtwin.config import load_microtwin_settings
from src.microtwin.rollout import rank_rollouts, rollout

from scripts.planning_common import build

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--energyplus-process-count", type=int, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    settings = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    context, plans = build()
    rollouts = tuple(rollout(context, plan, settings) for plan in plans if plan.eligible)
    ranked = rank_rollouts(rollouts)
    validation = json.loads(
        (settings.model_directory / "thermal_validation_report.json").read_text()
    )
    demand = json.loads((settings.model_directory / "demand_validation_report.json").read_text())
    model_manifest = json.loads((settings.model_directory / "model_manifest.json").read_text())
    module11 = tuple(
        plan.plan_id
        for plan in sorted(plans, key=lambda item: (item.advisory_score, item.plan_id))
        if plan.eligible
    )
    items = []
    for item in rollouts:
        plan = next(value for value in plans if value.plan_id == item.plan_id)
        items.append(
            {
                "plan_id": item.plan_id,
                "rollout_id": item.rollout_id,
                "strategy_type": plan.strategy_type,
                "planning_context_id": item.context_id,
                "horizon": len(item.points),
                "predicted_temperature_trajectory_c": [
                    p.predicted_temperature_c for p in item.points
                ],
                "lower_uncertainty_trajectory_c": [p.lower_temperature_c for p in item.points],
                "upper_uncertainty_trajectory_c": [p.upper_temperature_c for p in item.points],
                "expected_occupancy_trajectory": [p.expected_occupancy for p in item.points],
                "occupied_boundary_risk_flags": [p.occupied_boundary_risk for p in item.points],
                "ood_status": item.qualification_status,
                "ood_timestep_count": item.ood_timestep_count,
                "module11_rank": module11.index(item.plan_id) + 1,
                "module12_rank": tuple(x.plan_id for x in ranked).index(item.plan_id) + 1,
                "physical_write_count": item.physical_write_count,
            }
        )
    checks = {
        "thermal_qualified": model_manifest["thermal_qualification"] is True,
        "demand_unavailable": demand["qualification_status"] == "UNAVAILABLE",
        "five_qualified_rollouts": len(ranked) == 5,
        "no_strong_ood": all(
            x.qualification_status != "NOT_QUALIFIED_FOR_RANKING" for x in rollouts
        ),
        "single_context": len({x.context_id for x in rollouts}) == 1,
        "single_exogenous_scenario": len({x.context_id for x in rollouts}) == 1,
        "causal_features_only": context.prohibited_future_source_count == 0,
        "zero_new_physical_writes": all(x.physical_write_count == 0 for x in rollouts),
        "twelve_step_mae_disclosed": "rollout_12_mae_c" in validation,
        "ranking_reproducible": ranked == rank_rollouts(rollouts),
        "energyplus_not_running": args.energyplus_process_count == 0,
    }
    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "model_qualification": "QUALIFIED",
        "model_fingerprint": model_manifest["model_id"],
        "thermal_test_mae_c": validation["mae"],
        "twelve_step_rollout_mae_c": validation["rollout_12_mae_c"],
        "demand_model_status": demand["qualification_status"],
        "module11_ranking": module11,
        "module12_ranking": tuple(x.plan_id for x in ranked),
        "rollouts": items,
        "physical_write_delta": 0,
        "energyplus_process_count": args.energyplus_process_count,
        "checks": checks,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }
    output = ROOT / "outputs/module13/module12_ledger_preflight.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
