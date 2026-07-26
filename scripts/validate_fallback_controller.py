"""Independently validate completed Module 7 artifacts without rerunning EnergyPlus."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.control.config import load_fallback_settings  # noqa: E402
from src.control.models import SAFETY_GUARD_PENDING  # noqa: E402


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


def validate(config: Path, mode: str, output: Path | None = None) -> tuple[list[Check], Path]:
    root = config.resolve().parents[1]
    settings = load_fallback_settings(config, root)
    if output is None:
        output = (
            settings.output(mode)
            if mode in {"live_shadow", "live_control"}
            else settings.output_root / "replay_shadow/run_1"
        )
    summary_path = output / "fallback_controller_summary.json"
    checks = [Check("Summary exists", summary_path.is_file(), str(summary_path))]
    validation_path = output / "fallback_controller_validation_summary.json"
    if not summary_path.is_file():
        return checks, validation_path
    summary = json.loads(summary_path.read_text())
    database = Path(summary["database"])
    checks.extend(
        [
            Check("Mode", summary["mode"] == mode, str(summary["mode"])),
            Check(
                "Safety guard pending",
                summary["safety_guard_status"] == SAFETY_GUARD_PENDING,
                str(summary["safety_guard_status"]),
            ),
            Check("No LLM", summary.get("llm_calls", 0) == 0, str(summary.get("llm_calls", 0))),
            Check(
                "No network",
                summary.get("network_calls", 0) == 0,
                str(summary.get("network_calls", 0)),
            ),
            Check(
                "No plenum action",
                summary["plenum_action_count"] == 0,
                str(summary["plenum_action_count"]),
            ),
            Check("Database exists", database.is_file(), str(database)),
        ]
    )
    expected = int(settings.raw["execution"]["expected_annual_states"])
    expected_decisions = expected * (5 if mode != "live_control" else 1)
    if database.is_file():
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        run = connection.execute("SELECT * FROM controller_runs").fetchone()
        decision_count = int(
            connection.execute("SELECT COUNT(*) FROM control_decisions").fetchone()[0]
        )
        command_count = int(
            connection.execute("SELECT COUNT(*) FROM control_commands").fetchone()[0]
        )
        future = int(
            connection.execute(
                """SELECT COUNT(*) FROM control_decisions
                WHERE intended_effective_sequence<=based_on_state_sequence"""
            ).fetchone()[0]
        )
        plenum = int(
            connection.execute(
                """SELECT COUNT(*) FROM control_decisions
                WHERE target_zone_name='PLENUM-1' AND action_type='APPLY_SETPOINT'"""
            ).fetchone()[0]
        )
        bounds = int(
            connection.execute(
                """SELECT COUNT(*) FROM control_decisions
                WHERE approved_setpoint_celsius IS NOT NULL
                AND (approved_setpoint_celsius<? OR approved_setpoint_celsius>?)""",
                (settings.minimum_setpoint, settings.maximum_setpoint),
            ).fetchone()[0]
        )
        orphan_commands = int(
            connection.execute(
                """SELECT COUNT(*) FROM control_commands c LEFT JOIN control_decisions d
                ON d.decision_id=c.decision_id WHERE d.decision_id IS NULL"""
            ).fetchone()[0]
        )
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign = len(connection.execute("PRAGMA foreign_key_check").fetchall())
        actuator_identities = int(
            connection.execute(
                """SELECT COUNT(DISTINCT c.actuator_identity)
                FROM controller_events e JOIN control_commands c
                ON c.command_id=e.command_id WHERE e.event_type='SET'"""
            ).fetchone()[0]
        )
        outcomes = int(connection.execute("SELECT COUNT(*) FROM command_outcomes").fetchone()[0])
        connection.close()
        checks.extend(
            [
                Check(
                    "Completed run",
                    run is not None and run["status"] == "COMPLETED",
                    str(None if run is None else run["status"]),
                ),
                Check(
                    "State count",
                    int(summary.get("state_count", summary.get("input_state_count", 0)))
                    == expected,
                    str(summary.get("state_count", summary.get("input_state_count"))),
                ),
                Check("Decision count", decision_count == expected_decisions, str(decision_count)),
                Check("Command links", orphan_commands == 0, str(orphan_commands)),
                Check("No future state", future == 0, str(future)),
                Check("No plenum control", plenum == 0, str(plenum)),
                Check("Bounds", bounds == 0, str(bounds)),
                Check("Integrity", integrity == "ok", integrity),
                Check("Foreign keys", foreign == 0, str(foreign)),
                Check(
                    "Commands persisted",
                    command_count
                    == int(
                        summary["command_count"]
                        if "command_count" in summary
                        else summary["hypothetical_command_count"]
                    ),
                    str(command_count),
                ),
            ]
        )
        if mode == "live_shadow":
            checks.extend(
                [
                    Check(
                        "Shadow zero writes",
                        int(summary["set_call_count"]) == 0,
                        str(summary["set_call_count"]),
                    ),
                    Check(
                        "Shadow physical parity",
                        summary["physical_comparison_status"] == "PASS",
                        str(summary["physical_comparison_status"]),
                    ),
                ]
            )
        if mode == "live_control":
            checks.extend(
                [
                    Check(
                        "Single actuator",
                        actuator_identities <= 1 and int(summary["actuator_identity_count"]) == 1,
                        str(actuator_identities),
                    ),
                    Check(
                        "Real set calls",
                        int(summary["set_call_count"]) > 0,
                        str(summary["set_call_count"]),
                    ),
                    Check("Reset", int(summary["reset_count"]) > 0, str(summary["reset_count"])),
                    Check(
                        "Expiry or replacement",
                        int(summary["expiry_count"]) + int(summary.get("replacement_count", 0)) > 0,
                        str(summary.get("replacement_count", 0)),
                    ),
                    Check("Observed outcomes", outcomes > 0, str(outcomes)),
                    Check(
                        "API errors",
                        int(summary["api_error_count"]) == 0,
                        str(summary["api_error_count"]),
                    ),
                    Check(
                        "Callback errors",
                        int(summary["callback_error_count"]) == 0,
                        str(summary["callback_error_count"]),
                    ),
                ]
            )
    payload = {
        "mode": mode,
        "status": "PASS" if all(c.passed for c in checks) else "FAIL",
        "checks": [asdict(c) for c in checks],
    }
    validation_path.write_text(json.dumps(payload, indent=2) + "\n")
    return checks, validation_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--controller-config", type=Path, default=Path("config/fallback_controller.yaml")
    )
    parser.add_argument(
        "--mode", choices=("replay_shadow", "live_shadow", "live_control"), required=True
    )
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    config = (
        args.controller_config
        if args.controller_config.is_absolute()
        else root / args.controller_config
    )
    output = args.output_directory
    if output is not None and not output.is_absolute():
        output = root / output
    checks, path = validate(config, args.mode, output)
    for check in checks:
        print(f"[{'PASS' if check.passed else 'FAIL'}] {check.name}: {check.detail}")
    print(f"Validation summary: {path}")
    return 0 if all(c.passed for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
