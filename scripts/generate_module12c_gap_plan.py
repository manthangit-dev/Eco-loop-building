"""Generate the Module 12C implementation plan from the strict Module 12B audit."""

from __future__ import annotations

import json
from pathlib import Path

FINAL_REASONS = {
    "MT12-002": "missing_source_run",
    "MT12-003": "wrong_environment",
    "MT12-004": "missing_target_zone",
    "MT12-005": "warmup_rows_excluded",
    "MT12-006": "api_not_ready_rows_excluded",
    "MT12-009": "duplicate_callback_records",
    "MT12-010": "non_monotonic_timestamps",
    "MT12-011": "cross_environment_transition",
    "MT12-013": "missing_occupancy",
    "MT12-014": "missing_outdoor_temperature_c",
    "MT12-015": "missing_setpoint_c",
    "MT12-016": "missing_demand_w",
    "MT12-017": "invalid_units",
    "MT12-018": "nan_rejected",
    "MT12-019": "infinity_rejected",
    "MT12-027": "cross_environment_transition",
    "MT12-029": "missing_demand_w",
    "MT12-050": "occupied_error_group",
    "MT12-051": "unoccupied_error_group",
    "MT12-062": "occupied_recovery_rollout",
    "MT12-083": "rankings_agree",
    "MT12-089": "persisted_candidate_evaluated",
    "MT12-092": "bounded_rollout_response",
    "MT12-096": "mock_llm_explains_validation",
    "MT12-097": "mock_llm_recommends_ranked_candidate",
}

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "outputs/module12b/replay_fixture_audit.json"
OUTPUT = ROOT / "outputs/module12c/final_25_gap_plan.json"
GAP_CLASSES = {
    "CATEGORY_LEVEL_INVARIANT_ONLY",
    "CATEGORY_ONLY",
    "DOCUMENTATION_ONLY",
    "MISSING",
    "INSUFFICIENT_SHARED_FIXTURE",
    "COVERAGE_GAP",
    "SHARED_EXECUTABLE_FIXTURE",
}


def main() -> int:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    gap_ids = set(audit["coverage_gaps"])
    rows = [row for row in audit["requirements"] if row["scenario_id"] in gap_ids]
    if len(rows) != 25 or {row["scenario_id"] for row in rows} != gap_ids:
        raise SystemExit(f"expected 25 audited gaps, found {len(rows)}")
    plans = []
    for row in rows:
        sid = row["scenario_id"]
        slug = row["scenario_name"].rstrip(".").lower().replace(" ", "_").replace("-", "_")
        is_positive = sid in {
            "MT12-005",
            "MT12-006",
            "MT12-009",
            "MT12-027",
            "MT12-050",
            "MT12-051",
            "MT12-062",
            "MT12-083",
            "MT12-089",
            "MT12-092",
            "MT12-096",
            "MT12-097",
        }
        if sid == "MT12-002":
            entry = "src.microtwin.validation.validate_source_run"
        elif sid in {"MT12-011", "MT12-027"}:
            entry = "src.microtwin.validation.validate_transition_environments"
        elif sid in {"MT12-050", "MT12-051"}:
            entry = "src.microtwin.validation.validate_error_group"
        elif sid == "MT12-062":
            entry = "src.microtwin.rollout.rollout"
        elif sid == "MT12-083":
            entry = "src.microtwin.validation.validate_rankings_agree"
        elif sid in {"MT12-089", "MT12-092"}:
            entry = "src.mcp_server.service.MCPToolService.call"
        elif sid in {"MT12-096", "MT12-097"}:
            entry = "src.microtwin.validation.validate_advisory_claim"
        else:
            entry = "src.microtwin.validation.validate_aligned_telemetry"
        plans.append(
            {
                "requirement_id": row["original_requirement_number"],
                "scenario_id": sid,
                "scenario_name": row["scenario_name"],
                "category": row["category"],
                "current_shared_fixture": row["current_fixture_or_handler"],
                "reason_current_coverage_insufficient": (
                    "Only the shared _checks category summary executes; the named input "
                    "and boundary are not constructed."
                ),
                "exact_input_mutation": row["scenario_name"].rstrip("."),
                "production_entry_point": entry,
                "expected_status": "ACCEPTED" if is_positive else "REJECTED",
                "expected_reason_code": FINAL_REASONS[sid],
                "expected_policy_event": "module12c_fixture_evaluated",
                "expected_persistence_effect": "none",
                "expected_model_or_rollout_status": "UNCHANGED",
                "expected_physical_write_delta": 0,
                "expected_energyplus_process_delta": 0,
                "proposed_dedicated_fixture_name": f"module12c_{sid.lower().replace('-', '_')}",
                "proposed_test_name": f"test_{sid.lower().replace('-', '_')}_{slug}",
                "proposed_replay_handler": f"negative_fixtures.FACTORIES['{sid}']",
                "files_expected_to_change": [
                    "src/microtwin/validation.py",
                    "tests/fixtures/microtwin/negative_fixtures.py",
                    "tests/test_microtwin_final_gap_fixtures.py",
                    "tests/fixtures/microtwin/module12_replay_manifest.json",
                ],
            }
        )
    unresolved_ids = [str(plan["scenario_id"]) for plan in plans]
    payload: dict[str, object] = {
        "source": str(AUDIT.relative_to(ROOT)).replace("\\", "/"),
        "expected_gap_count": 25,
        "actual_gap_count": len(plans),
        "internally_consistent": True,
        "unresolved_ids": unresolved_ids,
        "gaps": plans,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("\n".join(unresolved_ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
