"""Stream Module 6 canonical states through Module 7 shadow policy."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.control.config import load_fallback_settings  # noqa: E402
from src.control.decision_engine import FallbackDecisionEngine  # noqa: E402
from src.control.models import (  # noqa: E402
    ControlCommand,
    ControlDecision,
    ControllerRunCompletion,
    ControllerRunMetadata,
    deterministic_hash,
)
from src.state.models import building_state_from_dict  # noqa: E402
from src.storage.controller_store import ControllerStore  # noqa: E402
from src.storage.queries import open_read_only  # noqa: E402


def replay(
    controller_config: Path, input_database: Path, output: Path, limit: int | None = None
) -> dict[str, object]:
    root = controller_config.resolve().parents[1]
    settings = load_fallback_settings(controller_config, root)
    output = output.resolve()
    output.relative_to(settings.output_root)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    run_id = f"module7-replay-{output.name}"
    database = output / str(settings.raw["storage"]["database_path"])
    engine = FallbackDecisionEngine(run_id, settings, shadow=True)
    metadata = ControllerRunMetadata(
        run_id,
        "module6-replay",
        "replay_shadow",
        datetime.now(UTC).isoformat(),
        json.loads((root / "models/MODEL_MANIFEST.json").read_text())["derived_baseline_sha256"],
        json.loads((root / "models/MODEL_MANIFEST.json").read_text())["weather_sha256"],
        limit or int(settings.raw["execution"]["expected_annual_states"]),
    )
    decisions = commands = 0
    reasons: Counter[str] = Counter()
    modes: Counter[str] = Counter()
    fingerprints: list[str] = []
    batch: list[tuple[ControlDecision, ControlCommand | None]] = []
    with ControllerStore(database, settings.output_root) as store:
        store.begin_run(metadata)
        with open_read_only(input_database) as source:
            cursor = source.execute("SELECT canonical_json FROM building_states ORDER BY sequence")
            for row in cursor:
                state = building_state_from_dict(json.loads(row[0]))
                for decision, command in engine.evaluate(state):
                    batch.append((decision, command))
                    if len(batch) >= int(settings.raw["storage"]["decision_batch_size"]):
                        store.append_batch(batch)
                        batch.clear()
                    decisions += 1
                    commands += int(command is not None)
                    reasons[decision.reason_code.value] += 1
                    modes[decision.controller_mode_after.value] += 1
                    fingerprints.append(
                        deterministic_hash(
                            {
                                "sequence": decision.decision_sequence,
                                "state": decision.based_on_state_sequence,
                                "state_fingerprint": decision.based_on_state_fingerprint,
                                "zone": decision.target_zone_id,
                                "before": decision.controller_mode_before,
                                "after": decision.controller_mode_after,
                                "reason": decision.reason_code,
                                "action": decision.action_type,
                                "requested": decision.requested_setpoint_celsius,
                                "approved": decision.approved_setpoint_celsius,
                                "command": None if command is None else command.fingerprint,
                            }
                        )
                    )
                if limit is not None and state.sequence >= limit:
                    break
        if batch:
            store.append_batch(batch)
        completion = ControllerRunCompletion(
            run_id,
            "COMPLETED",
            datetime.now(UTC).isoformat(),
            limit or int(settings.raw["execution"]["expected_annual_states"]),
            decisions,
            commands,
            0,
            0,
            0,
            0,
            0,
            0,
        )
        store.finalise(completion)
    summary: dict[str, object] = {
        "run_id": run_id,
        "mode": "replay_shadow",
        "input_state_count": completion.state_count,
        "decision_count": decisions,
        "hypothetical_command_count": commands,
        "plenum_action_count": 0,
        "actuator_write_count": 0,
        "reasons": dict(reasons),
        "modes": dict(modes),
        "decision_content_fingerprint": deterministic_hash({"items": fingerprints}),
        "database": str(database),
        "safety_guard_status": "not_implemented_module_8_pending",
        "llm_calls": 0,
        "network_calls": 0,
    }
    (output / "fallback_controller_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-config", type=Path, default=Path("config/state_bus.yaml"))
    parser.add_argument(
        "--controller-config", type=Path, default=Path("config/fallback_controller.yaml")
    )
    parser.add_argument("--input-database", type=Path)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    config = (
        args.controller_config
        if args.controller_config.is_absolute()
        else root / args.controller_config
    )
    source = (
        args.input_database
        or root / "data/output/module_6_state_bus/replay/current/thermoledger_state.db"
    )
    output = (
        args.output_directory
        or root / "data/output/module_7_fallback_controller/replay_shadow/run_1"
    )
    summary = replay(config, source, output, args.limit)
    if not args.quiet:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
