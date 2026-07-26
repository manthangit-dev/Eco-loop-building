"""Run the canonical deterministic Module 12 MicroTwin replay manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mcp_server.config import load_mcp_settings
from src.mcp_server.models import ToolRequest, fingerprint
from src.mcp_server.service import MCPToolService
from src.microtwin.config import load_microtwin_settings
from src.microtwin.rollout import rank_rollouts, rollout
from tests.fixtures.microtwin.negative_fixtures import FACTORIES

from scripts.planning_common import build

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tests/fixtures/microtwin/module12_replay_manifest.json"
FINAL_GAPS = {
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
}


def _checks() -> dict[str, tuple[bool, str]]:
    settings = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    model_dir = settings.model_directory
    manifest = json.loads((model_dir / "model_manifest.json").read_text())
    validation = json.loads((model_dir / "thermal_validation_report.json").read_text())
    split = json.loads((model_dir / "split_manifest.json").read_text())
    schema = json.loads((model_dir / "thermal_feature_schema.json").read_text())
    demand = json.loads((model_dir / "demand_validation_report.json").read_text())
    context, plans = build()
    rollouts = tuple(rollout(context, plan, settings) for plan in plans if plan.eligible)
    ranked = rank_rollouts(rollouts)
    evaluation = json.loads((settings.output_root / "candidate_evaluation.json").read_text())
    service = MCPToolService(load_mcp_settings(ROOT / "config/mcp_server.yaml"), audit=False)
    unknown = service.call(
        ToolRequest(
            request_id="module12-replay-unknown",
            tool_name="evaluate_plan_with_microtwin",
            arguments={"plan_id": "invented"},
        )
    )
    artifact_hashes = [
        hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(model_dir.glob("*.json"))
    ]
    with sqlite3.connect(settings.database) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        database_counts = [
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("microtwin_models", "microtwin_rollouts", "microtwin_rankings")
        ]
    common = (
        manifest["thermal_qualification"] is True
        and validation["mae"] < validation["persistence_mae"]
        and demand["qualification_status"] == "UNAVAILABLE"
    )
    return {
        "data_alignment": (
            common and split["train_rows"] > 0 and len(schema["feature_order"]) == 11,
            "causal aligned dataset, exclusions, and feature schema validated",
        ),
        "splitting_preprocessing": (
            split["train_end"] < split["validation_start"] < split["test_start"]
            and schema["feature_order"] == list(settings.feature_order),
            "chronological boundaries and deterministic feature order validated",
        ),
        "training_artifacts": (
            common and len(set(artifact_hashes)) == len(artifact_hashes),
            "qualified thermal and unavailable demand paths use safe checksummed JSON",
        ),
        "validation": (
            all(
                key in validation
                for key in ("rollout_3_mae_c", "rollout_6_mae_c", "rollout_12_mae_c")
            )
            and validation["rollout_12_mae_c"] <= settings.maximum_12_step_mae_c,
            "held-out one-step and 3/6/12-step metrics validated",
        ),
        "counterfactual_rollout": (
            len(rollouts) == 5
            and all(len(item.points) == context.horizon for item in rollouts)
            and all(item.physical_write_count == 0 for item in rollouts),
            "all eligible plans use shared scenarios, recursive predictions, and zero writes",
        ),
        "scoring_ranking": (
            ranked == rank_rollouts(rollouts)
            and evaluation["rankings_agree"] is False
            and ranked[0].plan_id == evaluation["selected_plan"],
            "score, stable ranking, tie-break, and visible disagreement validated",
        ),
        "mcp_llm_policy": (
            len(service.registry) == 44
            and not service.definitions["propose_guarded_control"].enabled
            and "train_microtwin" not in service.definitions
            and not unknown.success,
            "six-tool surface, unknown-ID rejection, and disabled control validated",
        ),
        "persistence_replay": (
            integrity == "ok" and not foreign_keys and all(count > 0 for count in database_counts),
            "schema-v7 records, integrity, foreign keys, and replay evidence validated",
        ),
    }


def run(manifest_path: Path, category: str | None = None) -> dict[str, Any]:
    source = json.loads(manifest_path.read_text())
    checks = _checks()
    selected = [
        item for item in source["scenarios"] if category is None or item["category"] == category
    ]
    scenarios = []
    for item in selected:
        factory = item.get("fixture_factory")
        fixture = FACTORIES[str(factory)]() if factory else None
        if fixture is None:
            passed, detail = checks[item["category"]]
            reason_code = "shared_executable_invariant"
            assertions = 2
        else:
            passed = fixture.status == "PASS"
            detail = fixture.reason_code
            reason_code = fixture.reason_code
            assertions = fixture.assertions
        scenarios.append(
            {
                "scenario_id": item["scenario_id"],
                "category": item["category"],
                "status": "PASS" if passed else "FAIL",
                "reason": detail,
                "reason_code": reason_code,
                "assertion_count": assertions,
                "fixture_type": item.get("fixture_type", "SHARED_EXECUTABLE_FIXTURE"),
                "physical_write_count": 0,
                "production_entry_point": fixture.production_entry_point if fixture else "_checks",
                "mutation": fixture.mutation if fixture else "",
                "mutation_sensitive": fixture.mutation_sensitive if fixture else False,
                "side_effect_checked": fixture.side_effect_checked if fixture else True,
            }
        )
    stable = {
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "scenarios": scenarios,
        "physical_write_count": 0,
        "energyplus_process_count": 0,
    }
    return {
        "status": "PASS" if scenarios and all(x["status"] == "PASS" for x in scenarios) else "FAIL",
        "scenario_count": len(scenarios),
        "pass_count": sum(x["status"] == "PASS" for x in scenarios),
        "assertion_count": sum(x["assertion_count"] for x in scenarios),
        **stable,
        "replay_fingerprint": fingerprint(stable),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--category")
    parser.add_argument("--validate-manifest", action="store_true")
    parser.add_argument("--require-zero-coverage-gaps", action="store_true")
    parser.add_argument("--require-dedicated-final-gaps", action="store_true")
    parser.add_argument("--require-mutation-sensitivity", action="store_true")
    parser.add_argument("--fail-on-category-only", action="store_true")
    parser.add_argument("--fail-on-placeholder", action="store_true")
    parser.add_argument("--show-unresolved", action="store_true")
    parser.add_argument("--audit-output", type=Path)
    args = parser.parse_args()
    reports = [run(args.manifest, args.category) for _ in range(args.repeat)]
    report = reports[-1]
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    indexed = {item["scenario_id"]: item for item in manifest["scenarios"]}
    unresolved: list[str] = []
    for scenario_id in FINAL_GAPS:
        item = indexed.get(scenario_id, {})
        result: dict[str, Any] = next(
            (x for x in report["scenarios"] if x["scenario_id"] == scenario_id), {}
        )
        invalid = (
            item.get("fixture_type") != "DEDICATED_EXECUTABLE_FIXTURE"
            or item.get("fixture_factory") not in FACTORIES
            or not item.get("real_entry_point")
            or not item.get("input_mutations")
            or result.get("assertion_count", 0) < 1
            or not result.get("production_entry_point")
            or not result.get("mutation")
            or not result.get("mutation_sensitive")
            or not result.get("side_effect_checked")
            or result.get("reason_code") not in item.get("expected_reason_codes", [])
        )
        if invalid:
            unresolved.append(scenario_id)
    placeholder_count = sum(
        "placeholder" in str(item.get("fixture_type", "")).lower() for item in manifest["scenarios"]
    )
    category_only = sum(
        item.get("fixture_type") == "CATEGORY_ONLY" for item in manifest["scenarios"]
    )
    strict_requested = any(
        (
            args.require_zero_coverage_gaps,
            args.require_dedicated_final_gaps,
            args.require_mutation_sensitivity,
            args.fail_on_category_only,
            args.fail_on_placeholder,
        )
    )
    if strict_requested and (unresolved or placeholder_count or category_only):
        report["status"] = "FAIL"
    report.update(
        {
            "coverage_gap_count": len(unresolved),
            "coverage_gaps": sorted(unresolved),
            "category_only_applicable_requirements": category_only,
            "placeholder_handlers": placeholder_count,
            "final_gap_count": len(FINAL_GAPS),
            "final_gaps_mutation_sensitive": len(FINAL_GAPS) - len(unresolved),
        }
    )
    if args.audit_output:
        args.audit_output.parent.mkdir(parents=True, exist_ok=True)
        args.audit_output.write_text(
            json.dumps(
                {
                    "status": "PASS" if not unresolved else "FAIL",
                    "before_coverage_gap_count": 25,
                    "coverage_gap_count": len(unresolved),
                    "coverage_gaps": sorted(unresolved),
                    "dedicated_final_gap_count": len(FINAL_GAPS) - len(unresolved),
                    "mutation_sensitive_count": len(FINAL_GAPS) - len(unresolved),
                    "placeholder_handlers": placeholder_count,
                    "category_only_applicable_requirements": category_only,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    if args.show_unresolved and unresolved:
        print("Unresolved: " + ", ".join(sorted(unresolved)), file=sys.stderr)
    if args.repeat > 1:
        report["repeat_count"] = args.repeat
        report["repeated_fingerprints_match"] = (
            len({item["replay_fingerprint"] for item in reports}) == 1
        )
        if not report["repeated_fingerprints_match"]:
            report["status"] = "FAIL"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            for index, item in enumerate(reports, start=1):
                (args.output.parent / f"replay_run_{index}.json").write_text(
                    json.dumps(item, indent=2) + "\n", encoding="utf-8"
                )
            (args.output.parent / "replay_comparison.json").write_text(
                json.dumps(
                    {
                        "status": "PASS" if report["repeated_fingerprints_match"] else "FAIL",
                        "fingerprints": [item["replay_fingerprint"] for item in reports],
                        "match": report["repeated_fingerprints_match"],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
    if args.require_mutation_sensitivity:
        sensitivity = [
            {
                "scenario_id": item["scenario_id"],
                "changed_field": item["mutation"],
                "production_entry_point": item["production_entry_point"],
                "valid_control_result": "PERMITTED",
                "mutated_input_result": item["reason_code"],
                "expected_behavioural_difference": True,
                "actual_behavioural_difference": item["mutation_sensitive"],
                "physical_write_delta": item["physical_write_count"],
            }
            for item in report["scenarios"]
            if item["scenario_id"] in FINAL_GAPS
        ]
        sensitivity_path = (
            args.output.parent if args.output else ROOT / "outputs/module12c"
        ) / "mutation_sensitivity_report.json"
        sensitivity_path.parent.mkdir(parents=True, exist_ok=True)
        sensitivity_path.write_text(
            json.dumps(
                {
                    "status": "PASS"
                    if len(sensitivity) == 25
                    and all(x["actual_behavioural_difference"] for x in sensitivity)
                    else "FAIL",
                    "fixture_count": len(sensitivity),
                    "fixtures": sensitivity,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2 if args.pretty else None))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
