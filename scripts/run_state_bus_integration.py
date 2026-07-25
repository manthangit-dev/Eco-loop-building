"""Run annual read-only EnergyPlus sensing through the canonical StateBus."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.energyplus.runner import EnergyPlusRunner  # noqa: E402
from src.energyplus.sensor_collector import SensorCollector  # noqa: E402
from src.energyplus.sensor_definitions import load_sensor_settings  # noqa: E402
from src.state.bus import StateBus  # noqa: E402
from src.state.config import StateSettings, load_state_settings  # noqa: E402
from src.state.models import RunCompletion, RunMetadata  # noqa: E402
from src.state.normalizer import StateNormalizer  # noqa: E402
from src.state.zone_classification import load_zone_classification  # noqa: E402
from src.storage.persistence_worker import StatePersistenceWorker  # noqa: E402
from src.storage.queries import open_read_only, table_counts  # noqa: E402
from src.storage.sqlite_store import SQLiteStateStore  # noqa: E402

from scripts.compare_runner_outputs import compare_outputs, comparison_exit_code  # noqa: E402


class LiveStatePublisher:
    def __init__(self, settings: StateSettings, state_config: Path, run_id: str) -> None:
        self.settings = settings
        self.state_config = state_config
        self.run_id = run_id
        self.bus = StateBus(settings.history_capacity)
        self.normalizer = StateNormalizer(
            run_id,
            str(settings.raw["execution"]["live_execution_mode"]),
            load_zone_classification(settings.root / "config/zone_classification.json"),
        )
        self.worker: StatePersistenceWorker | None = None
        self.subscription: int | None = None
        self.normalised_count = 0
        self.first_label = ""
        self.last_label = ""

    def before_run(self, api: Any, _state: Any, config: Any) -> None:
        metadata = RunMetadata(
            run_id=self.run_id,
            module=6,
            execution_mode=str(self.settings.raw["execution"]["live_execution_mode"]),
            status="RUNNING",
            started_at_utc=datetime.now(UTC).isoformat(),
            energyplus_version="EnergyPlus 26.1.0",
            api_version=str(api.api_version()),
            model_path="models/baseline/thermoledger_5zone_baseline.idf",
            model_checksum=config.model_sha256,
            weather_path=f"weather/input/{config.weather.name}",
            weather_checksum=config.weather_sha256,
            configuration_checksum=hashlib.sha256(self.state_config.read_bytes()).hexdigest(),
            expected_snapshot_count=self.settings.expected_snapshot_count,
            notes="Read-only live Module 6 state publication; no actuator callback.",
        )
        self.worker = StatePersistenceWorker(
            self.settings.database_path("live"),
            self.settings.output_root,
            metadata,
            queue_capacity=self.settings.queue_capacity,
            batch_size=self.settings.batch_size,
            enqueue_timeout_seconds=self.settings.enqueue_timeout_seconds,
            journal_mode=self.settings.journal_mode,
            busy_timeout_ms=self.settings.busy_timeout_ms,
        )
        self.worker.start()
        self.subscription = self.bus.subscribe(self.worker.enqueue)

    def register_callbacks(self, _api: Any, _state: Any) -> None:
        return

    def publish_snapshot(self, snapshot: Any) -> None:
        state = self.normalizer.normalize(snapshot)
        self.bus.publish(state)
        self.normalised_count += 1
        label = (
            f"{state.clock.month:02d}-{state.clock.day:02d} "
            f"{state.clock.hour:02d}:{state.clock.minute:02d}"
        )
        self.first_label = self.first_label or label
        self.last_label = label

    def close(self) -> None:
        if self.worker is None:
            self.bus.shutdown()
            return
        completion = RunCompletion(
            run_id=self.run_id,
            status="COMPLETED",
            finished_at_utc=datetime.now(UTC).isoformat(),
            persisted_snapshot_count=self.normalised_count,
            first_sequence=1,
            last_sequence=self.normalised_count,
            first_simulation_timestamp=self.first_label,
            last_simulation_timestamp=self.last_label,
            severe_count=0,
            fatal_count=0,
            callback_error_count=0,
            api_error_count=0,
            subscriber_error_count=int(self.bus.statistics()["subscriber_error_count"]),
            persistence_error_count=0,
            queue_drained=True,
        )
        self.worker.set_completion(completion)
        if self.subscription is not None:
            self.bus.unsubscribe(self.subscription)
        self.worker.stop()
        self.bus.shutdown()


class CompositeExtension:
    def __init__(self, extensions: tuple[Any, ...]) -> None:
        self.extensions = extensions

    def before_run(self, api: Any, state: Any, config: Any) -> None:
        for extension in self.extensions:
            extension.before_run(api, state, config)

    def register_callbacks(self, api: Any, state: Any) -> None:
        for extension in self.extensions:
            extension.register_callbacks(api, state)

    def close(self) -> None:
        for extension in reversed(self.extensions):
            extension.close()


def run_live(
    api_config: Path,
    sensor_config: Path,
    state_config: Path,
    *,
    no_clean: bool = False,
    quiet: bool = False,
    timeout: int | None = None,
    skip_physical_comparison: bool = False,
) -> tuple[bool, Path]:
    root = state_config.resolve().parents[1]
    state_settings = load_state_settings(state_config, root)
    sensor_settings = load_sensor_settings(sensor_config, root)
    sensor_settings = replace(
        sensor_settings,
        output_root=state_settings.output_root,
        output_directory=state_settings.live_output,
    )
    run_id = f"module6-live-{uuid4()}"
    publisher = LiveStatePublisher(state_settings, state_config, run_id)
    sensor = SensorCollector(sensor_settings, publisher.publish_snapshot)
    extension = CompositeExtension((publisher, sensor))
    result = EnergyPlusRunner(api_config).run(
        no_clean=no_clean,
        timeout_override=timeout,
        quiet=quiet,
        skip_comparison=True,
        output_root_override=state_settings.output_root,
        output_directory_override=state_settings.live_output,
        extension=extension,
    )
    if publisher.worker is None:
        raise RuntimeError("Live persistence worker was not initialized.")
    worker_stats = publisher.worker.statistics()
    bus_stats = publisher.bus.statistics()
    completion = RunCompletion(
        run_id=run_id,
        status="COMPLETED" if result.exit_code == 0 else "FAILED",
        finished_at_utc=result.finished_at,
        persisted_snapshot_count=int(worker_stats["persisted_count"]),
        first_sequence=1,
        last_sequence=publisher.normalised_count,
        first_simulation_timestamp=publisher.first_label,
        last_simulation_timestamp=publisher.last_label,
        severe_count=0,
        fatal_count=0,
        callback_error_count=len(sensor.callback_errors),
        api_error_count=sensor.registry.api_error_count,
        subscriber_error_count=int(bus_stats["subscriber_error_count"]),
        persistence_error_count=int(worker_stats["persistence_errors"]),
        queue_drained=bool(worker_stats["final_drained"]),
    )
    with SQLiteStateStore(
        state_settings.database_path("live"),
        state_settings.output_root,
        journal_mode=state_settings.journal_mode,
    ) as store:
        store.finalise_run(completion)
    sensor_summary = {
        **sensor.summary(),
        "run_id": result.run_id,
        "energyplus_exit_code": result.exit_code,
        "runner_status": result.status.value,
        "model_sha256": result.model_sha256,
        "weather_sha256": result.weather_sha256,
        "actuator_access_count": 0,
    }
    (state_settings.live_output / "sensor_extraction_summary.json").write_text(
        json.dumps(sensor_summary, indent=2) + "\n", encoding="utf-8"
    )
    physical_ok = True
    comparisons: list[Any] = []
    if not skip_physical_comparison:
        manifest = json.loads((root / "models/MODEL_MANIFEST.json").read_text())
        comparisons = compare_outputs(
            root / "data/output/module_4_sensor_extraction/current",
            state_settings.live_output,
            "thermoledger",
            str(manifest["derived_baseline_sha256"]),
            str(manifest["weather_sha256"]),
        )
        physical_ok = comparison_exit_code(comparisons) == 0
    with open_read_only(state_settings.database_path("live")) as connection:
        counts = table_counts(connection)
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    summary = {
        "run_id": run_id,
        "energyplus_run_id": result.run_id,
        "energyplus_exit_code": result.exit_code,
        "sensor_snapshot_count": sensor.counters.successful_snapshots,
        "normalised_state_count": publisher.normalised_count,
        "published_state_count": bus_stats["published_state_count"],
        "persisted_state_count": worker_stats["persisted_count"],
        "zone_row_count": counts["zone_states"],
        "first_sequence": 1,
        "last_sequence": publisher.normalised_count,
        "first_timestamp": publisher.first_label,
        "last_timestamp": publisher.last_label,
        "bus": bus_stats,
        "persistence": worker_stats,
        "database_path": str(state_settings.database_path("live")),
        "database_size_bytes": state_settings.database_path("live").stat().st_size,
        "integrity_check": integrity,
        "foreign_key_violation_count": len(foreign_keys),
        "physical_comparison_status": "PASS" if physical_ok else "FAIL",
        "physical_comparisons": [vars(item) for item in comparisons],
        "actuator_access_count": 0,
        "control_decision_count": 0,
    }
    summary_path = state_settings.live_output / "state_bus_run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    passed = (
        result.exit_code == 0
        and publisher.normalised_count == state_settings.expected_snapshot_count
        and worker_stats["persisted_count"] == publisher.normalised_count
        and counts["zone_states"] == publisher.normalised_count * state_settings.expected_zone_count
        and not sensor.callback_errors
        and not publisher.bus.subscriber_errors
        and integrity == "ok"
        and not foreign_keys
        and physical_ok
    )
    print(f"Run ID: {run_id}")
    print(f"EnergyPlus exit code: {result.exit_code}")
    lifecycle_counts = (
        sensor.counters.successful_snapshots,
        publisher.normalised_count,
        bus_stats["published_state_count"],
        worker_stats["persisted_count"],
    )
    print("Sensor/normalised/published/persisted: " + "/".join(map(str, lifecycle_counts)))
    print(f"Zone rows: {counts['zone_states']}")
    print(f"Database: {state_settings.database_path('live')}")
    print(f"Physical comparison: {'PASS' if physical_ok else 'FAIL'}")
    print("PASS" if passed else "FAIL")
    return passed, summary_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-config", type=Path, default=Path("config/api_runner.yaml"))
    parser.add_argument("--sensor-config", type=Path, default=Path("config/sensors.yaml"))
    parser.add_argument("--state-config", type=Path, default=Path("config/state_bus.yaml"))
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--skip-physical-comparison", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    passed, _ = run_live(
        resolve(args.api_config),
        resolve(args.sensor_config),
        resolve(args.state_config),
        no_clean=args.no_clean,
        quiet=args.quiet,
        timeout=args.timeout,
        skip_physical_comparison=args.skip_physical_comparison,
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
