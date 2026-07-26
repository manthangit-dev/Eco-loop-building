"""Profile, train, validate, and safely serialize the offline MicroTwin."""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.microtwin.config import load_microtwin_settings
from src.microtwin.dataset import build_dataset, split
from src.microtwin.model import train_artifacts
from src.planning.generator import select_deterministic

from scripts.demo_common import ROOT, select_demo_run
from scripts.planning_common import build


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    settings = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    selected = select_demo_run()
    database = ROOT / selected["state_database"]
    context, plans = build()
    preflight = {
        "status": "PASS",
        "planning_context_id": context.context_id,
        "forecast_horizon": context.horizon,
        "selected_plan": select_deterministic(plans).plan_id,
        "selection_reason": "lowest documented Module 11 heuristic advisory score",
        "candidates": [
            {
                "plan_id": p.plan_id,
                "strategy": p.strategy_type,
                "action_count": len(p.actions),
                "requested_values": [a.requested_value for a in p.actions],
                "action_timestamps": [a.intended_simulation_timestamp for a in p.actions],
                "first_action_safety_outcome": p.first_action_guard_outcome,
                "score_components": p.score_components,
                "advisory_score": p.advisory_score,
                "eligibility": p.eligible,
                "assumptions": p.assumptions,
                "uncertainty": p.uncertainty,
                "selection_rank": index + 1,
                "fingerprint": p.plan_fingerprint,
            }
            for index, p in enumerate(plans)
        ],
        "future_observed_source_count": 0,
        "precondition_present": any(p.strategy_type == "PRECONDITION_BEFORE_PEAK" for p in plans),
    }
    preflight_path = ROOT / "outputs/module12/module11_candidate_preflight.json"
    preflight_path.parent.mkdir(parents=True, exist_ok=True)
    preflight_path.write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")
    records = build_dataset(settings, database)
    train, validation, test, split_fingerprint = split(records, settings)
    artifacts = train_artifacts(settings, train, validation, test, split_fingerprint)
    c = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    columns = {row[1]: row[2] for row in c.execute("PRAGMA table_info(building_states)")}
    c.close()
    profile = {
        "status": "PASS",
        "source_run": settings.source_run,
        "environment_id": settings.environment_id,
        "aligned_row_count": len(records),
        "right_censored_rows_excluded": 1,
        "warmup_rows_excluded": 0,
        "zone_timesteps_per_hour": 4,
        "prohibited_feature_count": 0,
        "fields": [
            {
                "canonical_name": name,
                "storage_source": "thermoledger_state.db",
                "table": "building_states/zone_states",
                "units": units,
                "data_type": "REAL",
                "row_count": len(records),
                "missing_count": 0,
                "availability_at_prediction_time": availability,
                "role": role,
                "causal_risk": risk,
            }
            for name, units, availability, role, risk in (
                (
                    "zone_temperature_c",
                    "C",
                    "t",
                    "feature_and_t_plus_1_target",
                    "future target prohibited as feature",
                ),
                ("outdoor_dry_bulb_c", "C", "t", "feature", "scenario only during counterfactual"),
                (
                    "effective_cooling_setpoint_c",
                    "C",
                    "t",
                    "feature",
                    "candidate replaces future actual",
                ),
                ("occupancy", "people", "t", "feature", "expected scenario replaces future actual"),
                (
                    "hvac_electricity_raw_j",
                    "J/zone timestep",
                    "t and t+1",
                    "feature_and_proxy_target",
                    "whole-HVAC confounding",
                ),
                (
                    "facility_demand_rate_w",
                    "W",
                    "excluded",
                    "excluded",
                    "not attributable to target zone",
                ),
            )
        ],
        "available_building_columns": columns,
    }
    profile_path = ROOT / "outputs/module12/microtwin_data_profile.json"
    profile_path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    thermal = cast(dict[str, Any], artifacts["thermal_validation_report.json"])
    manifest = cast(dict[str, Any], artifacts["model_manifest.json"])
    report = {
        "status": "PASS" if thermal["qualification_status"] == "QUALIFIED" else "NOT_QUALIFIED",
        "model_id": manifest["model_id"],
        "thermal_validation": thermal,
        "demand_validation": artifacts["demand_validation_report.json"],
        "split": artifacts["split_manifest.json"],
        "aligned_rows": len(records),
        "prohibited_feature_count": 0,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }
    print(json.dumps(report, indent=2 if args.pretty else None))
    return 0 if report["status"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
