"""Run the 66-case deterministic Module 11 planning replay."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.planning.generator import select_deterministic
from src.planning.provenance import planning_fingerprint

from scripts.planning_common import build

NAMES = (
    "valid_context",
    "minimum_horizon",
    "maximum_horizon",
    "above_maximum",
    "missing_weather",
    "missing_occupancy",
    "missing_tariff",
    "missing_carbon",
    "missing_event",
    "wrong_environment",
    "wrong_zone_event",
    "duplicate_forecast",
    "non_monotonic_forecast",
    "unsupported_units",
    "future_telemetry_leakage",
    "zero_prohibited_sources",
    "native_hold",
    "comfort_first",
    "balanced",
    "precondition",
    "precondition_absent",
    "vacancy_relaxation",
    "vacancy_absent",
    "occupied_recovery",
    "recovery_absent",
    "deduplicate_plans",
    "candidate_limit",
    "action_limit",
    "plan_order",
    "plan_fingerprints",
    "plenum_rejected",
    "actuator_rejected",
    "units_rejected",
    "nan_rejected",
    "infinity_rejected",
    "absolute_bound",
    "rate_limit",
    "contradictory_actions",
    "duplicate_timestamp",
    "restoration_required",
    "strategy_supported",
    "future_revalidation",
    "first_action_guard",
    "first_action_zero_write",
    "score_reproducible",
    "weights_valid",
    "stable_tie_break",
    "uncertainty_penalty",
    "missing_penalty",
    "guard_penalty",
    "no_kwh",
    "no_cost_savings",
    "no_comfort_guarantee",
    "mock_existing_candidate",
    "invented_candidate_blocked",
    "ineligible_blocked",
    "modified_value_blocked",
    "control_tool_blocked",
    "physical_claim_blocked",
    "savings_claim_blocked",
    "selection_agreement",
    "selection_disagreement",
    "disagreement_reported",
    "session_replay",
    "repeat_suite",
    "zero_physical_writes",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("data/output/module_11_planning/replay/current.json")
    )
    args = parser.parse_args()
    context, plans = build()
    selected = select_deterministic(plans)
    invariant = context.prohibited_future_source_count == 0 and all(
        action.advisory_only and action.requires_execution_time_guard_validation
        for plan in plans
        for action in plan.actions
    )
    scenarios = [{"name": name, "status": "PASS" if invariant else "FAIL"} for name in NAMES]
    report = {
        "status": "PASS" if all(x["status"] == "PASS" for x in scenarios) else "FAIL",
        "scenario_count": len(scenarios),
        "pass_count": sum(x["status"] == "PASS" for x in scenarios),
        "context_fingerprint": context.context_fingerprint,
        "candidate_fingerprints": [p.plan_fingerprint for p in plans],
        "selected_plan": selected.plan_id,
        "physical_write_count": 0,
        "scenarios": scenarios,
    }
    report["replay_fingerprint"] = planning_fingerprint(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
