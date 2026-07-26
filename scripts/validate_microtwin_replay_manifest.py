"""Validate Module 12B manifest schema and executable fixture coverage."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.fixtures.microtwin.negative_fixtures import FACTORIES

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests/fixtures/microtwin/module12_replay_manifest.json"
FIELDS = {
    "scenario_id",
    "requirement_ids",
    "category",
    "name",
    "purpose",
    "fixture_type",
    "fixture_path",
    "fixture_factory",
    "real_entry_point",
    "input_mutations",
    "expected_status",
    "expected_reason_codes",
    "expected_policy_events",
    "expected_persistence_effect",
    "expected_model_qualification",
    "expected_rollout_status",
    "expected_physical_write_delta",
    "expected_energyplus_process_delta",
    "deterministic_fingerprint_required",
    "assertion_reference",
}

# These original requirements still need input-specific executable fixtures. A broad
# category check must never be promoted to shared coverage for them.
REQUIRES_DEDICATED = {
    "MT12-002", "MT12-003", "MT12-004", "MT12-005", "MT12-006", "MT12-009",
    "MT12-010", "MT12-011", "MT12-013", "MT12-014", "MT12-015", "MT12-016",
    "MT12-017", "MT12-018", "MT12-019", "MT12-027", "MT12-029", "MT12-050",
    "MT12-051", "MT12-062", "MT12-083", "MT12-089", "MT12-092", "MT12-096",
    "MT12-097",
}


def main() -> int:
    started = time.monotonic()
    payload: dict[str, Any] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    audit = []
    gaps = []
    for item in payload["scenarios"]:
        missing = sorted(FIELDS - item.keys())
        factory = item.get("fixture_factory")
        valid_class = item.get("fixture_type") in {
            "DEDICATED_EXECUTABLE_FIXTURE",
            "SHARED_EXECUTABLE_FIXTURE",
        }
        executable = (
            factory in FACTORIES
            if item.get("fixture_type") == "DEDICATED_EXECUTABLE_FIXTURE"
            else item.get("real_entry_point") == "_checks"
        )
        wrongly_shared = (
            item["scenario_id"] in REQUIRES_DEDICATED
            and item.get("fixture_type") != "DEDICATED_EXECUTABLE_FIXTURE"
        )
        if missing or not valid_class or not executable or wrongly_shared:
            gaps.append(item["scenario_id"])
        audit.append(
            {
                "original_requirement_number": item["requirement_ids"][0],
                "scenario_id": item["scenario_id"],
                "scenario_name": item["name"],
                "category": item["category"],
                "current_fixture_or_handler": item["fixture_path"],
                "concrete_mutation_or_input": item["input_mutations"],
                "real_code_path_executed": item["real_entry_point"],
                "expected_result": item["expected_status"],
                "expected_reason_code": item["expected_reason_codes"],
                "expected_database_effect": item["expected_persistence_effect"],
                "expected_physical_write_count": item["expected_physical_write_delta"],
                "current_implementation_class": item["fixture_type"],
            "required_correction": (
                "NONE"
                if not missing and executable and not wrongly_shared
                else "DEDICATED_FIXTURE_REQUIRED"
            ),
                "final_implementation_class": item["fixture_type"],
            }
        )
    report = {
        "status": "PASS" if not gaps and payload["scenario_count"] == len(audit) else "FAIL",
        "scenario_count": len(audit),
        "dedicated_fixture_count": sum(
            x["final_implementation_class"] == "DEDICATED_EXECUTABLE_FIXTURE" for x in audit
        ),
        "shared_fixture_count": sum(
            x["final_implementation_class"] == "SHARED_EXECUTABLE_FIXTURE" for x in audit
        ),
        "coverage_gap_count": len(gaps),
        "coverage_gaps": gaps,
        "runtime_seconds": round(time.monotonic() - started, 3),
        "requirements": audit,
    }
    output = ROOT / "outputs/module12b/replay_fixture_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({key: value for key, value in report.items() if key != "requirements"}, indent=2)
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
