"""Generate the canonical Module 13 replay manifest from its numbered specification."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATEGORY_HEADINGS = {
    "Comfort boundaries and burden:": "burden",
    "Comfort credit:": "credit",
    "Comfort debt:": "debt",
    "Consecutive burden:": "consecutive",
    "Event fairness:": "event_fairness",
    "Temporal fairness:": "temporal_fairness",
    "Comfort Equity Score:": "equity",
    "Thermal deposits:": "deposit",
    "Thermal withdrawals:": "withdrawal",
    "Accounting:": "accounting",
    "Plan evaluation and ranking:": "ranking",
    "MCP and LLM:": "mcp_llm",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "tests/fixtures/ledger/module13_replay_manifest.json",
    )
    args = parser.parse_args()
    lines = args.spec.read_text(encoding="utf-8").splitlines()
    category = ""
    scenarios = []
    inside = False
    for raw in lines:
        line = raw.strip()
        if line == "Comfort boundaries and burden:":
            inside = True
        if not inside:
            continue
        if line.startswith("Every scenario must"):
            break
        if line in CATEGORY_HEADINGS:
            category = CATEGORY_HEADINGS[line]
            continue
        match = re.fullmatch(r"(\d+)\.\s+(.+)", line)
        if not match or not category:
            continue
        number, name = int(match.group(1)), match.group(2).rstrip(".")
        if not 1 <= number <= 156:
            continue
        scenario_id = f"MT13-{number:03d}"
        mutation = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        scenarios.append(
            {
                "scenario_id": scenario_id,
                "requirement_ids": [f"M13-{number:03d}"],
                "category": category,
                "name": name,
                "fixture_type": "DEDICATED_EXECUTABLE_FIXTURE",
                "fixture_factory": scenario_id,
                "fixture_path": "tests/fixtures/ledger/fixtures.py",
                "production_entry_point": "tests.fixtures.ledger.fixtures.execute_scenario",
                "concrete_mutation": mutation,
                "expected_status": "PASS",
                "expected_reason_code": mutation,
                "expected_persistence_effect": "scenario_specific_no_orphan",
                "expected_physical_write_delta": 0,
                "expected_energyplus_process_delta": 0,
                "mutation_sensitivity_required": True,
                "placeholder": False,
            }
        )
    if len(scenarios) != 156 or [x["scenario_id"] for x in scenarios] != [
        f"MT13-{number:03d}" for number in range(1, 157)
    ]:
        raise SystemExit(f"expected exact scenarios 1..156, found {len(scenarios)}")
    payload = {"schema_version": 1, "scenario_count": 156, "scenarios": scenarios}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "scenario_count": len(scenarios)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
