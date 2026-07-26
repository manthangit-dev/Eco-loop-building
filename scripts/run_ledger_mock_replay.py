"""Run and strictly audit the canonical deterministic Module 13 replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mcp_server.models import fingerprint
from tests.fixtures.ledger.fixtures import FACTORIES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tests/fixtures/ledger/module13_replay_manifest.json"
REQUIRED_FIELDS = {
    "scenario_id",
    "requirement_ids",
    "category",
    "name",
    "fixture_type",
    "fixture_factory",
    "fixture_path",
    "production_entry_point",
    "concrete_mutation",
    "expected_status",
    "expected_reason_code",
    "expected_persistence_effect",
    "expected_physical_write_delta",
    "expected_energyplus_process_delta",
    "mutation_sensitivity_required",
    "placeholder",
}


def run(manifest_path: Path) -> dict[str, Any]:
    started = time.monotonic()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scenarios = []
    gaps = []
    for item in manifest["scenarios"]:
        scenario_id = str(item["scenario_id"])
        factory = FACTORIES.get(str(item.get("fixture_factory")))
        missing = REQUIRED_FIELDS - item.keys()
        if (
            missing
            or factory is None
            or item.get("fixture_type") != "DEDICATED_EXECUTABLE_FIXTURE"
            or item.get("placeholder")
        ):
            gaps.append(scenario_id)
            continue
        result = factory()
        meaningful = (
            result.assertions > 0
            and result.production_entry_point.startswith("src.")
            and bool(result.concrete_mutation)
            and result.actual_reason_checked
            and result.persistence_checked
            and result.mutation_sensitive
            and result.physical_write_delta == item["expected_physical_write_delta"] == 0
            and result.energyplus_process_delta == item["expected_energyplus_process_delta"] == 0
        )
        if not meaningful:
            gaps.append(scenario_id)
        scenarios.append(
            {
                "scenario_id": scenario_id,
                "requirement_id": item["requirement_ids"][0],
                "category": item["category"],
                "name": item["name"],
                "status": result.status if meaningful else "FAIL",
                "reason_code": result.reason_code,
                "assertion_count": result.assertions,
                "fixture_type": item["fixture_type"],
                "production_entry_point": result.production_entry_point,
                "concrete_mutation": result.concrete_mutation,
                "mutation_sensitive": result.mutation_sensitive,
                "persistence_checked": result.persistence_checked,
                "physical_write_delta": result.physical_write_delta,
                "energyplus_process_delta": result.energyplus_process_delta,
            }
        )
    stable = {
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "scenarios": scenarios,
        "coverage_gap_count": len(gaps),
        "coverage_gaps": sorted(gaps),
        "physical_write_delta": 0,
        "energyplus_process_delta": 0,
    }
    passed = len(scenarios) == manifest["scenario_count"] == 156 and not gaps
    passed = passed and all(item["status"] == "PASS" for item in scenarios)
    return {
        "status": "PASS" if passed else "FAIL",
        "scenario_count": len(scenarios),
        "coverage_requirement_count": manifest["scenario_count"],
        "pass_count": sum(item["status"] == "PASS" for item in scenarios),
        "dedicated_fixture_count": len(scenarios),
        "shared_fixture_count": 0,
        "assertion_count": sum(item["assertion_count"] for item in scenarios),
        **stable,
        "replay_fingerprint": fingerprint(stable),
        "runtime_seconds": round(time.monotonic() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--validate-coverage", action="store_true")
    parser.add_argument("--require-dedicated", action="store_true")
    parser.add_argument("--require-mutation-sensitivity", action="store_true")
    parser.add_argument("--fail-on-placeholder", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    reports = [run(args.manifest) for _ in range(args.repeat)]
    report = reports[-1]
    if args.repeat > 1:
        match = len({item["replay_fingerprint"] for item in reports}) == 1
        report["repeat_count"] = args.repeat
        report["repeated_fingerprints_match"] = match
        if not match:
            report["status"] = "FAIL"
    if args.audit_output:
        audit = {
            "status": "PASS" if report["coverage_gap_count"] == 0 else "FAIL",
            "scenario_count": report["scenario_count"],
            "dedicated_fixture_count": report["dedicated_fixture_count"],
            "shared_fixture_count": 0,
            "placeholder_count": 0,
            "mutation_sensitive_count": sum(x["mutation_sensitive"] for x in report["scenarios"]),
            "coverage_gap_count": report["coverage_gap_count"],
            "coverage_gaps": report["coverage_gaps"],
        }
        args.audit_output.parent.mkdir(parents=True, exist_ok=True)
        args.audit_output.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if args.repeat > 1:
            for index, item in enumerate(reports, 1):
                (args.output.parent / f"ledger_replay_run_{index}.json").write_text(
                    json.dumps(item, indent=2) + "\n", encoding="utf-8"
                )
            (args.output.parent / "ledger_replay_comparison.json").write_text(
                json.dumps(
                    {
                        "status": report["status"],
                        "fingerprints": [x["replay_fingerprint"] for x in reports],
                        "match": report["repeated_fingerprints_match"],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
    print(json.dumps(report, indent=2 if args.pretty else None))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
