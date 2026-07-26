"""Mechanically normalize the canonical Module 12B replay manifest schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tests/fixtures/microtwin/module12_replay_manifest.json"

DEDICATED = {
    **{
        scenario_id: scenario_id
        for scenario_id in (
            "MT12-002",
            "MT12-003",
            "MT12-004",
            "MT12-005",
            "MT12-006",
            "MT12-009",
            "MT12-010",
            "MT12-011",
            "MT12-013",
            "MT12-014",
            "MT12-015",
            "MT12-016",
            "MT12-017",
            "MT12-018",
            "MT12-019",
            "MT12-027",
            "MT12-029",
            "MT12-050",
            "MT12-051",
            "MT12-062",
            "MT12-083",
            "MT12-089",
            "MT12-092",
            "MT12-096",
            "MT12-097",
        )
    },
    "MT12-020": "future_temperature",
    "MT12-034": "demand_unavailable",
    "MT12-037": "schema_mismatch",
    "MT12-040": "insufficient_data",
    "MT12-042": "persistence_failure",
    "MT12-043": "checksum_mismatch",
    "MT12-044": "unsafe_artifact",
    "MT12-069": "ood_outdoor",
    "MT12-070": "ood_setpoint",
    "MT12-086": "unqualified_ranking",
    "MT12-090": "unknown_plan",
    "MT12-094": "mcp_training",
    "MT12-095": "mcp_control",
    "MT12-098": "unknown_rollout",
    "MT12-099": "modified_score",
    "MT12-100": "claim_energyplus",
    "MT12-101": "claim_energy",
    "MT12-102": "claim_physical",
    "MT12-105": "zero_write",
}
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


def normalize(item: dict[str, Any]) -> dict[str, Any]:
    scenario_id = str(item["scenario_id"])
    name = str(item.get("name", item.get("description", scenario_id)))
    factory = item.get("fixture_factory") or DEDICATED.get(scenario_id)
    dedicated = factory is not None
    expected_reason = item.get("expected_reason_code")
    reasons = (
        [FINAL_REASONS[scenario_id]]
        if scenario_id in FINAL_REASONS
        else item.get("expected_reason_codes", [] if expected_reason is None else [expected_reason])
    )
    return {
        "scenario_id": scenario_id,
        "requirement_ids": item.get("requirement_ids", [scenario_id.replace("MT12-", "M12-")]),
        "category": item["category"],
        "name": name,
        "purpose": item.get("purpose", f"Execute and assert: {name}"),
        "fixture_type": "DEDICATED_EXECUTABLE_FIXTURE"
        if dedicated
        else item.get("fixture_type", "SHARED_EXECUTABLE_FIXTURE"),
        "fixture_path": "tests/fixtures/microtwin/negative_fixtures.py"
        if dedicated
        else item.get("fixture_path", "scripts/run_microtwin_mock_replay.py"),
        "fixture_factory": factory,
        "real_entry_point": f"negative_fixtures.FACTORIES['{factory}']"
        if dedicated
        else item.get("real_entry_point", "_checks"),
        "input_mutations": [name] if dedicated else item.get("input_mutations", []),
        "expected_status": item.get("expected_status", "PASS"),
        "expected_reason_codes": reasons,
        "expected_policy_events": item.get("expected_policy_events", []),
        "expected_persistence_effect": item.get(
            "expected_persistence_effect", "no_unsafe_mutation"
        ),
        "expected_model_qualification": item.get("expected_model_qualification", "QUALIFIED"),
        "expected_rollout_status": item.get("expected_rollout_status", "UNCHANGED_OR_EXPECTED"),
        "expected_physical_write_delta": item.get("expected_physical_write_delta", 0),
        "expected_energyplus_process_delta": item.get("expected_energyplus_process_delta", 0),
        "deterministic_fingerprint_required": item.get("deterministic_fingerprint_required", True),
        "assertion_reference": item.get(
            "assertion_reference", "scripts/run_microtwin_mock_replay.py"
        ),
    }


def main() -> int:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    payload["schema_version"] = 2
    payload["scenarios"] = [normalize(item) for item in payload["scenarios"]]
    payload["scenario_count"] = len(payload["scenarios"])
    PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "scenario_count": payload["scenario_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
