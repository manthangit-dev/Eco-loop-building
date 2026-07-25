"""Run one Module 5 control or intervention simulation."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.energyplus.actuator_controller import ActuatorController  # noqa: E402
from src.energyplus.actuator_definitions import load_actuator_settings  # noqa: E402
from src.energyplus.actuator_plan import build_plan  # noqa: E402
from src.energyplus.runner import EnergyPlusRunner  # noqa: E402
from src.energyplus.sensor_collector import SensorCollector  # noqa: E402
from src.energyplus.sensor_definitions import load_sensor_settings  # noqa: E402


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


def run_experiment(
    api_config: Path,
    sensor_config: Path,
    actuator_config: Path,
    run_type: str,
    *,
    no_clean: bool = False,
    quiet: bool = False,
    timeout: int | None = None,
) -> int:
    root = actuator_config.resolve().parents[1]
    actuator_settings = load_actuator_settings(actuator_config, root)
    plan = build_plan(actuator_settings)
    output = (
        actuator_settings.control_output
        if run_type == "control"
        else actuator_settings.intervention_output
    )
    sensor_settings = load_sensor_settings(sensor_config, root)
    sensor_settings = replace(
        sensor_settings,
        output_root=actuator_settings.output_root,
        output_directory=output,
    )
    sensor = SensorCollector(sensor_settings)
    controller = ActuatorController(
        actuator_settings,
        plan,
        run_type,
        output,
        tuple(zone for zone in sensor_settings.zones if not zone.startswith("PLENUM")),
    )
    extension = CompositeExtension((sensor, controller))
    result = EnergyPlusRunner(api_config).run(
        no_clean=no_clean,
        timeout_override=timeout,
        quiet=quiet,
        skip_comparison=True,
        output_root_override=actuator_settings.output_root,
        output_directory_override=output,
        extension=extension,
    )
    sensor_summary = {
        **sensor.summary(),
        "run_id": result.run_id,
        "energyplus_exit_code": result.exit_code,
        "runner_status": result.status.value,
        "model_sha256": result.model_sha256,
        "weather_sha256": result.weather_sha256,
        "actuator_access_count": 1,
    }
    (output / "sensor_extraction_summary.json").write_text(
        json.dumps(sensor_summary, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        **controller.summary(),
        "run_id": result.run_id,
        "energyplus_exit_code": result.exit_code,
        "runner_status": result.status.value,
        "sensor_snapshot_count": sensor.counters.successful_snapshots,
        "sensor_callback_error_count": len(sensor.callback_errors),
        "model_sha256": result.model_sha256,
        "weather_sha256": result.weather_sha256,
    }
    (output / actuator_settings.summary_json).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Run type: {run_type}")
    print(f"EnergyPlus exit code: {result.exit_code}")
    print(f"Actuator handle: {controller.registry.handle}")
    print(f"Set calls: {controller.counters.set_calls}")
    print(f"Reset calls: {controller.counters.reset_calls}")
    print(f"Sensor snapshots: {sensor.counters.successful_snapshots}")
    print(f"Callback errors: {controller.counters.callback_error_count}")
    passed = (
        result.exit_code == 0
        and not controller.callback_errors
        and not sensor.callback_errors
        and sensor.counters.successful_snapshots == sensor_settings.minimum_snapshots
        and controller.registry.handle is not None
        and (run_type == "control" or controller.counters.set_calls > 0)
    )
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-config", type=Path, default=Path("config/api_runner.yaml"))
    parser.add_argument("--sensor-config", type=Path, default=Path("config/sensors.yaml"))
    parser.add_argument("--actuator-config", type=Path, default=Path("config/actuators.yaml"))
    parser.add_argument("--run-type", choices=("control", "intervention"), required=True)
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--timeout", type=int)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    return run_experiment(
        resolve(args.api_config),
        resolve(args.sensor_config),
        resolve(args.actuator_config),
        args.run_type,
        no_clean=args.no_clean,
        quiet=args.quiet,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
