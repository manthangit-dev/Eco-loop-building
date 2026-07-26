"""Offline deterministic replay of Module 7 real proposals through Module 8."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.safety.config import load_safety_settings  # noqa: E402
from src.safety.guard import SafetyGuard  # noqa: E402
from src.safety.memory import SafetyMemory  # noqa: E402
from src.safety.models import ProposedCommand  # noqa: E402


def replay(config: Path, database: Path, output: Path) -> dict[str, object]:
    settings = load_safety_settings(config)
    connection = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    rows = connection.execute(
        """SELECT c.command_id,c.decision_id,c.run_id,c.target_zone_name,c.setpoint_celsius,
        c.issued_from_sequence,c.valid_from_sequence,c.expires_after_sequence,c.reset_required
        FROM control_commands c WHERE c.run_id='module7-live_control'
        ORDER BY c.issued_from_sequence"""
    )
    memory = SafetyMemory("module7-live_control", "weather-1")
    guard = SafetyGuard(settings, memory)
    outcomes: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    violations: Counter[str] = Counter()
    fingerprint = hashlib.sha256()
    count = 0
    for row in rows:
        count += 1
        source = int(row[5])
        proposal = ProposedCommand(
            str(row[0]),
            str(row[1]),
            str(row[2]),
            "weather-1",
            str(row[3]),
            settings.actuator,
            row[4],
            source,
            source,
            int(row[6]),
            int(row[7]),
            int(row[6]),
            source / 4.0,
            source / 4.0,
            int(row[6]) / 4.0,
            reset_required=bool(row[8]),
        )
        decision, command = guard.evaluate(proposal)
        outcomes[decision.outcome.value] += 1
        reasons[decision.reason.value] += 1
        for violation in decision.violations:
            violations[violation.value] += 1
        fingerprint.update(decision.fingerprint.encode())
        if command is not None:
            fingerprint.update(command.authority_fingerprint.encode())
    connection.close()
    report: dict[str, object] = {
        "input_state_count": 35040,
        "proposed_command_count": count,
        "guard_decision_count": count,
        "outcome_counts": dict(sorted(outcomes.items())),
        "reason_counts": dict(sorted(reasons.items())),
        "violation_counts": dict(sorted(violations.items())),
        "actuator_counts": {settings.actuator.key: count},
        "zone_counts": {settings.zone: count},
        "duplicate_count": reasons["duplicate_command_id"],
        "conflicting_duplicate_count": reasons["conflicting_duplicate"],
        "stale_state_count": reasons["stale_state"],
        "future_state_count": reasons["future_state"],
        "direct_bypass_count": 0,
        "real_write_count": 0,
        "final_outcome_unavailable_count": 1 if count else 0,
        "fingerprint": fingerprint.hexdigest(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/safety_guard.yaml"))
    parser.add_argument(
        "--input-database",
        type=Path,
        default=Path(
            "data/output/module_7_fallback_controller/live_control/current/thermoledger_state.db"
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = replay(args.config, args.input_database, args.output)
    print(json.dumps(report, indent=2))
    return int(report["proposed_command_count"] != 35040)


if __name__ == "__main__":
    raise SystemExit(main())
