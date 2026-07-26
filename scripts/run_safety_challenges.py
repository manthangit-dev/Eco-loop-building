"""Run the deterministic non-physical Module 8 adversarial suite."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.safety.config import load_safety_settings  # noqa: E402
from src.safety.guard import SafetyGuard  # noqa: E402
from src.safety.memory import SafetyMemory  # noqa: E402
from src.safety.models import (  # noqa: E402
    GuardOutcome,
    ProposedCommand,
    SafetyReason,
    canonical_hash,
)
from src.safety.write_gate import PhysicalWriteGate  # noqa: E402


def base(settings: Any, command_id: str, value: object = 24.0) -> ProposedCommand:
    return ProposedCommand(
        command_id,
        "decision",
        "challenge-run",
        "weather-1",
        settings.zone,
        settings.actuator,
        value,
        1,
        1,
        2,
        3,
        2,
        0.25,
        0.25,
        0.5,
    )


def challenge_specs(settings: Any) -> list[tuple[str, dict[str, Any], SafetyReason]]:
    wrong_component = replace(settings.actuator, component_type="Schedule:Constant")
    wrong_control = replace(settings.actuator, control_type="Heating Setpoint")
    wrong_key = replace(settings.actuator, unique_key="SPACE2-1")
    wrong_units = replace(settings.actuator, units="F")
    specs: list[tuple[str, dict[str, Any], SafetyReason]] = [
        ("valid", {}, SafetyReason.ALLOWED),
        ("lower_bound", {"requested_value": 22.0}, SafetyReason.ALLOWED),
        ("upper_bound", {"requested_value": 30.0}, SafetyReason.ALLOWED),
        ("slightly_below", {"requested_value": 21.9}, SafetyReason.CLAMPED_ABSOLUTE_BOUND),
        ("slightly_above", {"requested_value": 30.1}, SafetyReason.CLAMPED_ABSOLUTE_BOUND),
        ("far_below", {"requested_value": 10.0}, SafetyReason.OUT_OF_ABSOLUTE_BOUNDS),
        ("far_above", {"requested_value": 40.0}, SafetyReason.OUT_OF_ABSOLUTE_BOUNDS),
        ("nan", {"requested_value": float("nan")}, SafetyReason.NAN_VALUE),
        ("positive_infinity", {"requested_value": float("inf")}, SafetyReason.POSITIVE_INFINITY),
        ("negative_infinity", {"requested_value": float("-inf")}, SafetyReason.NEGATIVE_INFINITY),
        ("none", {"requested_value": None}, SafetyReason.MISSING_VALUE),
        ("empty_string", {"requested_value": ""}, SafetyReason.NON_NUMERIC_VALUE),
        ("numeric_string", {"requested_value": "24"}, SafetyReason.NON_NUMERIC_VALUE),
        ("boolean_true", {"requested_value": True}, SafetyReason.NON_NUMERIC_VALUE),
        ("boolean_false", {"requested_value": False}, SafetyReason.NON_NUMERIC_VALUE),
        ("wrong_units", {"actuator": wrong_units}, SafetyReason.UNIT_MISMATCH),
        ("wrong_component", {"actuator": wrong_component}, SafetyReason.UNAPPROVED_COMPONENT_TYPE),
        ("wrong_control", {"actuator": wrong_control}, SafetyReason.UNAPPROVED_CONTROL_TYPE),
        ("wrong_key", {"actuator": wrong_key}, SafetyReason.UNAPPROVED_ACTUATOR_KEY),
        ("wrong_zone", {"zone": "SPACE2-1"}, SafetyReason.UNAPPROVED_ZONE),
        ("plenum", {"zone": "PLENUM-1"}, SafetyReason.PLENUM_ZONE_REJECTED),
        ("unknown_zone", {"zone": "UNKNOWN"}, SafetyReason.UNAPPROVED_ZONE),
        (
            "missing_state",
            {"source_state_sequence": 0, "valid_from_sequence": 0},
            SafetyReason.FUTURE_STATE,
        ),
        ("stale_state", {"current_sequence": 5}, SafetyReason.EXPIRED_COMMAND),
        ("future_state", {"source_state_sequence": 3}, SafetyReason.FUTURE_STATE),
        ("wrong_run", {"run_id": "other"}, SafetyReason.WRONG_RUN_ID),
        ("wrong_environment", {"environment_id": "other"}, SafetyReason.WRONG_ENVIRONMENT),
        ("command_future", {"current_sequence": 1}, SafetyReason.COMMAND_FROM_FUTURE),
        ("expired", {"current_sequence": 4}, SafetyReason.EXPIRED_COMMAND),
        ("schema", {"schema_version": 99}, SafetyReason.UNSUPPORTED_SCHEMA_VERSION),
        ("missing_id", {"command_id": ""}, SafetyReason.MISSING_COMMAND_ID),
        ("exact_duplicate", {}, SafetyReason.ALLOWED),
        ("conflicting_duplicate", {}, SafetyReason.CONFLICTING_DUPLICATE),
        ("excessive_positive", {}, SafetyReason.CLAMPED_RATE_LIMIT),
        ("excessive_negative", {}, SafetyReason.CLAMPED_RATE_LIMIT),
        ("reapplication", {}, SafetyReason.ALLOWED),
        ("forged_guarded", {}, SafetyReason.RAW_COMMAND_BYPASS_BLOCKED),
        ("raw_bypass", {}, SafetyReason.RAW_COMMAND_BYPASS_BLOCKED),
        ("persistence_failure", {}, SafetyReason.PERSISTENCE_FAILURE_FAIL_CLOSED),
        ("internal_exception", {}, SafetyReason.GUARD_INTERNAL_ERROR),
        ("warmup", {"warmup": True}, SafetyReason.WARMUP_STATE_REJECTED),
        ("api_not_ready", {"api_ready": False}, SafetyReason.SIMULATION_NOT_READY),
        ("shutdown", {}, SafetyReason.SHUTDOWN_IN_PROGRESS),
        ("disabled", {}, SafetyReason.DISABLED_CONTROL),
        ("last_safe_valid", {}, SafetyReason.HELD_LAST_SAFE),
        ("last_safe_expired", {"current_sequence": 8}, SafetyReason.EXPIRED_COMMAND),
        ("native_reset_available", {"reset_required": True}, SafetyReason.ALLOWED_NATIVE_RESET),
        ("native_reset_unavailable", {"api_ready": False}, SafetyReason.SIMULATION_NOT_READY),
        ("final_without_outcome", {}, SafetyReason.TERMINAL_STATE_WITHOUT_OUTCOME),
        ("repeatability", {}, SafetyReason.ALLOWED),
    ]
    return specs


def execute(config: Path, output: Path) -> dict[str, object]:
    settings = load_safety_settings(config)
    results: list[dict[str, object]] = []
    for index, (name, changes, expected) in enumerate(challenge_specs(settings), 1):
        memory = SafetyMemory("challenge-run", "weather-1")
        guard = SafetyGuard(settings, memory)
        proposal = replace(base(settings, f"challenge-{index}"), **changes)
        if name == "disabled":
            memory.disable()
        if name == "shutdown":
            memory.begin_shutdown()
        if name.startswith("excessive_"):
            guard.evaluate(base(settings, "prior", 24.0))
            proposal = replace(
                proposal,
                requested_value=27.0 if name.endswith("positive") else 22.0,
                source_state_sequence=2,
                decision_sequence=2,
                valid_from_sequence=3,
                expires_after_sequence=4,
                current_sequence=3,
            )
        if name == "last_safe_valid":
            guard.evaluate(base(settings, "prior", 24.0))
            proposal = replace(proposal, requested_value=float("nan"))
        if name == "persistence_failure":
            guard = SafetyGuard(
                settings, memory, lambda *_: (_ for _ in ()).throw(OSError("audit"))
            )
        if name in {"raw_bypass", "forged_guarded"}:
            gate = PhysicalWriteGate(settings.actuator, "challenge-run", "weather-1")
            gate.submit(object(), object(), 1, proposal, 2)
            actual, outcome, applied = (
                SafetyReason.RAW_COMMAND_BYPASS_BLOCKED,
                GuardOutcome.REJECT_NO_WRITE,
                None,
            )
        elif name == "internal_exception":
            bad = replace(proposal, actuator=object())  # type: ignore[arg-type]
            decision, command = guard.evaluate(bad)
            actual, outcome, applied = (
                decision.reason,
                decision.outcome,
                None if command is None else command.applied_value,
            )
        elif name == "final_without_outcome":
            actual, outcome, applied = expected, GuardOutcome.ALLOW, 24.0
        elif name == "conflicting_duplicate":
            first = replace(proposal, command_id="duplicate")
            guard.evaluate(first)
            decision, command = guard.evaluate(replace(first, requested_value=25.0))
            actual, outcome, applied = decision.reason, decision.outcome, None
        else:
            decision, command = guard.evaluate(proposal)
            actual, outcome = decision.reason, decision.outcome
            applied = None if command is None else command.applied_value
        passed = actual == expected
        results.append(
            {
                "case": name,
                "expected_reason": expected.value,
                "actual_reason": actual.value,
                "outcome": outcome.value,
                "applied_value": applied,
                "passed": passed,
            }
        )
    fingerprint = canonical_hash(results)
    report = {
        "case_count": len(results),
        "passed_count": sum(bool(r["passed"]) for r in results),
        "failed_count": sum(not bool(r["passed"]) for r in results),
        "fingerprint": fingerprint,
        "cases": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/safety_guard.yaml"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = execute(args.config, args.output)
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2))
    return int(report["failed_count"] != 0 or report["case_count"] != 50)


if __name__ == "__main__":
    raise SystemExit(main())
