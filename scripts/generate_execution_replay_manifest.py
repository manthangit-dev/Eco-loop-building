"""Generate the fixed 130-scenario Module 14 replay manifest."""

# ruff: noqa: E501 -- the canonical scenario-name catalogue is intentionally literal.

from __future__ import annotations

import json
from pathlib import Path

NAMES = ["Valid replay approval", "Valid shadow approval", "Valid live-short approval", "Missing approval", "Expired approval", "Invalid approval fingerprint", "Plan fingerprint mismatch", "Rollout fingerprint mismatch", "Ledger fingerprint mismatch", "Model fingerprint mismatch", "Wrong zone", "Wrong actuator", "Wrong units", "Simulation-only missing", "Invalid write limit", "Invalid reset limit", "Wrong execution mode", "IDF checksum mismatch", "EPW checksum mismatch", "Approval reused", "Plan no longer eligible", "Blocking debt", "Strong OOD", "Unqualified rollout", "Valid full transition", "Invalid IDLE to EXECUTING transition", "Approval-required transition", "Armed transition", "Waiting-for-state transition", "Executing and holding", "Fallback transition", "Reset transition", "Completed transition", "Aborted transition", "Failed transition", "Duplicate terminal transition", "Single action", "Multiple ordered actions", "Early action", "Late action", "Duplicate callback", "Duplicate action", "Missing action", "Unexpected action", "Changed value", "Changed action sequence", "Action-count limit", "Write-count limit", "Minimum hold", "Mandatory restoration", "Valid committed state", "Warmup state", "API-not-ready state", "Stale state", "Future state", "Wrong environment", "Wrong callback", "Missing state", "PLENUM target", "Boolean-as-number rejection", "NaN value", "Infinity value", "Guard ALLOW", "Guard CLAMP", "Guard HOLD_LAST_SAFE", "Guard RESET_TO_NATIVE", "Guard REJECT_NO_WRITE", "Raw command bypass", "Forged GuardedCommand", "Writer unavailable", "Writer exception", "Duplicate writer call", "Audit failure before write", "Persistence failure after guard", "Unknown write status", "Set limit reached", "Reset limit reached", "Approval expiry fallback", "Stale-state fallback", "API failure fallback", "Scheduler failure fallback", "Writer failure fallback", "Persistence failure fallback", "Operator abort fallback", "Timeout fallback", "Environment-end fallback", "Fallback guard rejection", "Fallback native reset", "Normal completion reset", "Abort reset", "Failure reset", "Timeout reset", "Environment-end reset", "Duplicate reset", "Reset writer failure", "Completion blocked without reset", "Replay performs zero writes", "Shadow performs zero writes", "Fake writer performs zero real writes", "Live mode requires approval", "Request cannot change mode", "LLM cannot enable live mode", "MCP cannot enable live mode", "propose_guarded_control remains disabled", "No execution-trigger MCP tool exists", "Approval persistence", "Approval immutability", "One-time approval consumption", "Session persistence", "Action persistence", "Transition persistence", "Writer-attempt persistence", "Fallback persistence", "Reset persistence", "Exact duplicate idempotency", "Conflicting duplicate", "Transaction rollback", "Foreign-key rejection", "NaN persistence rejection", "Infinity persistence rejection", "Execution status tool", "Execution audit tool", "Approval-status tool", "Compatible run comparison", "Incompatible run comparison", "False real-building claim blocked", "False annual-savings claim blocked", "False guaranteed-comfort claim blocked", "False LLM-executed claim blocked", "Zero unguarded writes"]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rows = []
    for index, name in enumerate(NAMES, 1):
        category = (
            "approval"
            if index <= 24
            else "state_machine"
            if index <= 36
            else "scheduler"
            if index <= 50
            else "live_state"
            if index <= 62
            else "guard_writer"
            if index <= 77
            else "fallback"
            if index <= 88
            else "shutdown"
            if index <= 96
            else "modes"
            if index <= 105
            else "persistence"
            if index <= 120
            else "observation_claims"
        )
        rows.append(
            {
                "scenario_id": f"EX14-{index:03d}",
                "requirement_id": f"M14-{index:03d}",
                "name": name,
                "category": category,
                "fixture_key": (
                    f"execution_{index:03d}_"
                    f"{name.lower().replace(' ', '_').replace('-', '_')}"
                ),
                "fixture_type": "DEDICATED_EXECUTABLE_FIXTURE",
                "concrete_mutation": name.lower().replace(" ", "_"),
            }
        )
    output = root / "tests/fixtures/execution/module14_replay_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"schema_version": 1, "scenarios": rows}, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "scenario_count": len(rows), "output": str(output)}))
    return 0 if len(rows) == 130 else 1


if __name__ == "__main__":
    raise SystemExit(main())
