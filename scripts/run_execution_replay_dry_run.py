"""Execute the approved plan through Module 8 with zero physical writes."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.execution.config import load_execution_settings
from src.execution.models import ExecutionApproval, ExecutionMode, TrustedLiveState
from src.execution.orchestrator import ExecutionOrchestrator, FakeWriter
from src.storage.execution_store import ExecutionStore

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/module14/replay_dry_run.json"
    )
    args = parser.parse_args()
    settings = load_execution_settings(ROOT / "config/execution_orchestrator.yaml")
    approval = ExecutionApproval.model_validate_json(args.approval.read_text(encoding="utf-8"))
    state = TrustedLiveState(
        execution_session_id=f"replay-{approval.approval_id[:16]}",
        run_id="module8-live-control",
        environment_id=approval.permitted_environment,
        current_state_id=19346,
        current_simulation_timestamp="07-21 12:30",
        simulation_time_hours=12.5,
        current_zone_temperature=25.6110683850401,
        current_effective_cooling_setpoint=30.0,
        current_occupancy=0.0,
        api_ready=True,
        warmup=False,
        callback_identity="end_zone_timestep_after_zone_reporting",
        target_actuator_identity=approval.actuator_identity,
        current_plan_action_index=0,
        current_sequence=19346,
    )
    report = ExecutionOrchestrator(settings, FakeWriter()).execute(
        approval, ExecutionMode.REPLAY_DRY_RUN, (state,)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    with sqlite3.connect(settings.database) as connection:
        ExecutionStore(connection).persist_report(report)
    print(json.dumps(report.model_dump(mode="json"), indent=2))
    return 0 if report.status == "PASS" and report.physical_set_calls == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
