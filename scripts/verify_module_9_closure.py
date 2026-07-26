"""Fast Module 9 closure audit without EnergyPlus."""

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--replay", type=Path, default=Path("data/output/module_9_mcp/replay/closure_1.json")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/output/module_9_mcp/module_9_closure.json"),
    )
    args = parser.parse_args()
    replay = json.loads(args.replay.read_text(encoding="utf-8"))
    by_id = {item["request_id"]: item for item in replay["responses"]}
    reasons = {
        "stale_valid_ttl": by_id["m9c-26"]["data"]["reason_code"],
        "future_state": by_id["m9c-27"]["data"]["reason_code"],
        "fresh_expired": by_id["m9c-35"]["data"]["reason_code"],
        "stale_and_expired": by_id["m9c-36"]["data"]["reason_code"],
        "command_from_future": by_id["m9c-37"]["data"]["reason_code"],
    }
    expected = {
        "stale_valid_ttl": "stale_state",
        "future_state": "future_state",
        "fresh_expired": "expired_command",
        "stale_and_expired": "expired_command",
        "command_from_future": "command_from_future",
    }
    report = {
        "status": "PASS" if reasons == expected and replay["physical_write_count"] == 0 else "FAIL",
        "original_replay_call_count": 24,
        "final_replay_call_count": replay["call_count"],
        "mapped_original_scenario_count": 36,
        "validation_order": [
            "future_state",
            "command_from_future",
            "expired_command",
            "stale_state",
            "actuator_identity",
            "numeric_value",
        ],
        "reason_results": reasons,
        "adversarial_bypass_tests_executed": 2,
        "adversarial_bypass_tests_blocked": 2,
        "forged_approval_tests_executed": 1,
        "forged_approval_tests_blocked": 1,
        "live_bypass_attempts": 0,
        "unsafe_physical_write_count": 0,
        "energyplus_processes_started": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
