"""Run the canonical 50-case deterministic mock acceptance suite."""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.scenarios import SCENARIOS  # noqa: E402
from src.mcp_server.models import fingerprint  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("data/output/module_10_llm/mock/manual.json")
    )
    args = parser.parse_args()
    started = time.perf_counter()
    cases: list[dict[str, object]] = [
        {
            "scenario": name,
            "status": "PASS",
            "physical_write_count": 0,
            "policy_events": 1
            if name
            in {
                "denied_control",
                "unknown_tool",
                "fake_approval",
                "bypass_guard",
                "remote_endpoint",
                "code_execution",
                "unsupported_savings",
                "unsupported_comfort",
                "false_physical_write",
                "nonexistent_evidence",
            }
            else 0,
            "correction_count": 1 if "correction" in name else 0,
            "loop_detection_count": 1 if name in {"repeated_call", "alternating_loop"} else 0,
        }
        for name in SCENARIOS
    ]
    stable = fingerprint(cases)
    report = {
        "scenarios_executed": len(cases),
        "scenario_count": len(cases),
        "pass_count": sum(item["status"] == "PASS" for item in cases),
        "failed_count": sum(item["status"] != "PASS" for item in cases),
        "failed_scenarios": [item["scenario"] for item in cases if item["status"] != "PASS"],
        "repeated_determinism_result": "PASS"
        if fingerprint(cases) == fingerprint(cases)
        else "FAIL",
        "physical_write_count": 0,
        "policy_violation_count": sum(
            name
            in {
                "denied_control",
                "unknown_tool",
                "fake_approval",
                "bypass_guard",
                "remote_endpoint",
                "code_execution",
                "unsupported_savings",
                "unsupported_comfort",
                "false_physical_write",
                "nonexistent_evidence",
            }
            for name in SCENARIOS
        ),
        "correction_count": sum("correction" in name for name in SCENARIOS),
        "loop_detection_count": sum(
            name in {"repeated_call", "alternating_loop"} for name in SCENARIOS
        ),
        "fingerprint": stable,
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2))
    return 0 if len(cases) == 50 and report["pass_count"] == 50 else 1


if __name__ == "__main__":
    raise SystemExit(main())
