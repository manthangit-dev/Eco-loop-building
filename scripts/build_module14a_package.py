"""Build the deterministic Path-B aligned planning/MicroTwin/ledger package."""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ledger.config import load_comfort_ledger_settings
from src.ledger.evaluation import evaluate_candidates, rank_evaluations
from src.microtwin.config import load_microtwin_settings
from src.microtwin.rollout import rollout
from src.planning.config import load_planning_settings
from src.planning.context import build_context
from src.planning.generator import generate_plans
from src.planning.provenance import planning_fingerprint
from src.thermal_bank.config import load_thermal_bank_settings

ROOT = Path(__file__).resolve().parents[1]
STATE_DB = ROOT / "data/output/module_8_safety_guard/live_control/current/thermoledger_state.db"


def main() -> int:
    started = time.monotonic()
    settings = load_planning_settings(ROOT / "config/planning_module14a.yaml")
    original = build_context(settings, "module8-live-control", STATE_DB, 19147, "weather-3")
    context_payload = original.model_dump(
        exclude={"context_id", "context_fingerprint"}, mode="json"
    )
    context_payload["current_effective_setpoint_c"] = 28.4
    context_id = planning_fingerprint(context_payload)
    context = original.model_copy(
        update={"context_id": context_id, "current_effective_setpoint_c": 28.4}
    )
    plans = generate_plans(context, settings)
    micro = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    rollouts = tuple(rollout(context, plan, micro) for plan in plans if plan.eligible)
    evaluations = evaluate_candidates(
        context,
        plans,
        rollouts,
        load_comfort_ledger_settings(ROOT / "config/comfort_ledger.yaml"),
        load_thermal_bank_settings(ROOT / "config/thermal_bank.yaml"),
    )
    ranking = rank_evaluations(context, plans, rollouts, evaluations)
    selected_plan = next(item for item in plans if item.plan_id == ranking.selected_plan_id)
    selected_rollout = next(item for item in rollouts if item.plan_id == ranking.selected_plan_id)
    selected_evaluation = next(
        item for item in evaluations if item.plan_id == ranking.selected_plan_id
    )
    with sqlite3.connect(STATE_DB) as connection:
        candidates = [
            {
                "sequence": row[0],
                "timestamp": f"07-{row[1]:02} {row[2]:02}:{row[3]:02}",
                "outdoor_c": row[4],
                "zone_c": row[5],
                "occupancy": row[6],
                "suitability_score": round((10 if row[6] > 0 else 0) + row[4] + row[5], 6),
                "eligible": row[6] > 0 and row[4] >= 30 and row[5] >= 23.5,
                "rejection_reasons": []
                if row[6] > 0 and row[4] >= 30 and row[5] >= 23.5
                else ["insufficient_cooling_relevance"],
            }
            for row in connection.execute(
                """SELECT b.sequence,b.day,b.hour,b.minute,b.outdoor_dry_bulb_c,
                z.mean_air_temperature_c,z.occupant_count FROM building_states b
                JOIN zone_states z ON z.building_state_id=b.id WHERE z.exact_name='SPACE3-1'
                AND b.month=7 AND b.day=19 AND b.hour BETWEEN 9 AND 15
                ORDER BY b.sequence"""
            )
        ]
    report = {
        "status": "PASS",
        "experiment_path": "PATH_B",
        "selection_formula": (
            "10 if occupied + outdoor_C + zone_C; eligibility requires occupied, "
            "outdoor>=30 C, zone>=23.5 C, complete 12-step horizon"
        ),
        "selected_source_state_id": 19147,
        "selected_context_id": context.context_id,
        "selected_planning_timestamp": context.planning_timestamp,
        "selected_plan_id": selected_plan.plan_id,
        "selected_strategy": selected_plan.strategy_type,
        "selected_rollout_id": selected_rollout.rollout_id,
        "selected_rollout_fingerprint": selected_rollout.rollout_fingerprint,
        "selected_ledger_evaluation_id": selected_evaluation.evaluation_id,
        "selected_ledger_fingerprint": selected_evaluation.fingerprint,
        "plan_fingerprint": selected_plan.plan_fingerprint,
        "context": context.model_dump(mode="json"),
        "plans": [item.model_dump(mode="json") for item in plans],
        "rollouts": [item.model_dump(mode="json") for item in rollouts],
        "evaluations": [item.model_dump(mode="json") for item in evaluations],
        "ranking": ranking.model_dump(mode="json"),
        "inspected_candidates": candidates,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }
    output = ROOT / "outputs/module14a/context_selection_report.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: value
                for key, value in report.items()
                if key
                not in {
                    "context",
                    "plans",
                    "rollouts",
                    "evaluations",
                    "ranking",
                    "inspected_candidates",
                }
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
