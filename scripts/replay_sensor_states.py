"""Replay validated Module 4 JSONL through the real StateBus and SQLite worker."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.state.bus import StateBus  # noqa: E402
from src.state.config import load_state_settings  # noqa: E402
from src.state.models import RunCompletion, RunMetadata  # noqa: E402
from src.state.normalizer import StateNormalizer, snapshot_from_dict  # noqa: E402
from src.state.zone_classification import load_zone_classification  # noqa: E402
from src.storage.persistence_worker import StatePersistenceWorker  # noqa: E402
from src.storage.queries import open_read_only, table_counts  # noqa: E402


def _prepare(output: Path, root: Path) -> None:
    output.relative_to(root)
    if output.exists():
        archive = root / "archive"
        archive.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        shutil.move(str(output), str(archive / f"replay_{stamp}"))
    output.mkdir(parents=True)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def replay(state_config: Path, limit: int | None = None) -> tuple[bool, Path]:
    root = state_config.resolve().parents[1]
    settings = load_state_settings(state_config, root)
    _prepare(settings.replay_output, settings.output_root)
    source = root / "data/output/module_4_sensor_extraction/current/sensor_snapshots.jsonl"
    source_hash_before = _sha256_file(source)
    module4_metadata = json.loads((source.parent / "run_metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "models/MODEL_MANIFEST.json").read_text())
    run_id = f"module6-replay-{uuid4()}"
    bus = StateBus(settings.history_capacity)
    normalizer = StateNormalizer(
        run_id,
        str(settings.raw["execution"]["replay_execution_mode"]),
        load_zone_classification(root / "config/zone_classification.json"),
    )
    metadata = RunMetadata(
        run_id=run_id,
        module=6,
        execution_mode=str(settings.raw["execution"]["replay_execution_mode"]),
        status="RUNNING",
        started_at_utc=datetime.now(UTC).isoformat(),
        energyplus_version=str(module4_metadata["energyplus_version"]),
        api_version=str(module4_metadata["api_version"]),
        model_path="models/baseline/thermoledger_5zone_baseline.idf",
        model_checksum=str(manifest["derived_baseline_sha256"]),
        weather_path=f"weather/input/{manifest['weather_filename']}",
        weather_checksum=str(manifest["weather_sha256"]),
        configuration_checksum=hashlib.sha256(state_config.read_bytes()).hexdigest(),
        expected_snapshot_count=limit or settings.expected_snapshot_count,
        notes="Full Module 4 JSONL replay; no EnergyPlus or actuator access.",
    )
    worker = StatePersistenceWorker(
        settings.database_path("replay"),
        settings.output_root,
        metadata,
        queue_capacity=settings.queue_capacity,
        batch_size=settings.batch_size,
        enqueue_timeout_seconds=settings.enqueue_timeout_seconds,
        journal_mode=settings.journal_mode,
        busy_timeout_ms=settings.busy_timeout_ms,
    )
    worker.start()
    subscription = bus.subscribe(worker.enqueue)
    count = 0
    first_label = ""
    last_label = ""
    try:
        with source.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    snapshot = snapshot_from_dict(json.loads(line))
                    state = normalizer.normalize(snapshot)
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise RuntimeError(f"Replay line {line_number}: {exc}") from exc
                bus.publish(state)
                count += 1
                label = (
                    f"{state.clock.month:02d}-{state.clock.day:02d} "
                    f"{state.clock.hour:02d}:{state.clock.minute:02d}"
                )
                first_label = first_label or label
                last_label = label
                if limit is not None and count >= limit:
                    break
        completion = RunCompletion(
            run_id=run_id,
            status="COMPLETED",
            finished_at_utc=datetime.now(UTC).isoformat(),
            persisted_snapshot_count=count,
            first_sequence=1,
            last_sequence=count,
            first_simulation_timestamp=first_label,
            last_simulation_timestamp=last_label,
            severe_count=0,
            fatal_count=0,
            callback_error_count=0,
            api_error_count=0,
            subscriber_error_count=int(bus.statistics()["subscriber_error_count"]),
            persistence_error_count=0,
            queue_drained=True,
        )
        worker.set_completion(completion)
        bus.unsubscribe(subscription)
        worker.stop()
    finally:
        bus.shutdown()
    source_hash_after = _sha256_file(source)
    with open_read_only(settings.database_path("replay")) as connection:
        counts = table_counts(connection)
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    summary = {
        "run_id": run_id,
        "mode": "replay",
        "input_snapshot_count": count,
        "normalised_state_count": count,
        "published_state_count": bus.statistics()["published_state_count"],
        "persisted_state_count": worker.statistics()["persisted_count"],
        "zone_row_count": counts["zone_states"],
        "bus": bus.statistics(),
        "persistence": worker.statistics(),
        "database_path": str(settings.database_path("replay")),
        "database_size_bytes": settings.database_path("replay").stat().st_size,
        "integrity_check": integrity,
        "foreign_key_violation_count": len(foreign_keys),
        "source_unchanged": source_hash_before == source_hash_after,
        "actuator_access_count": 0,
        "control_decision_count": 0,
    }
    summary_path = settings.replay_output / "state_bus_run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    passed = (
        count == (limit or settings.expected_snapshot_count)
        and worker.statistics()["persisted_count"] == count
        and counts["zone_states"] == count * settings.expected_zone_count
        and integrity == "ok"
        and not foreign_keys
        and not bus.subscriber_errors
    )
    print(f"Run ID: {run_id}")
    persisted_count = worker.statistics()["persisted_count"]
    print(f"Input/normalised/published/persisted: {count}/{count}/{count}/{persisted_count}")
    print(f"Zone rows: {counts['zone_states']}")
    print(f"Database: {settings.database_path('replay')}")
    print("PASS" if passed else "FAIL")
    return passed, summary_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-config", type=Path, default=Path("config/state_bus.yaml"))
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    config = args.state_config if args.state_config.is_absolute() else root / args.state_config
    passed, _ = replay(config, args.limit)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
