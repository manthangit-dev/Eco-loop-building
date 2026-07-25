"""Run read-only live EnergyPlus sensor extraction for Module 4."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.energyplus.run_result import RunStatus  # noqa: E402
from src.energyplus.runner import EnergyPlusRunner  # noqa: E402
from src.energyplus.sensor_collector import SensorCollector  # noqa: E402
from src.energyplus.sensor_definitions import load_sensor_settings  # noqa: E402

from scripts.compare_sensor_run_to_baseline import compare_sensor_run  # noqa: E402
from scripts.validate_baseline import validation_exit_code  # noqa: E402
from scripts.validate_sensor_extraction import validate_sensor_output  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-config", type=Path, default=Path("config/api_runner.yaml"))
    parser.add_argument("--sensor-config", type=Path, default=Path("config/sensors.yaml"))
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--skip-baseline-comparison", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    sensor_config = (
        args.sensor_config.resolve()
        if args.sensor_config.is_absolute()
        else (root / args.sensor_config).resolve()
    )
    settings = load_sensor_settings(sensor_config, root)
    collector = SensorCollector(settings)
    result = EnergyPlusRunner(args.api_config).run(
        no_clean=args.no_clean,
        timeout_override=args.timeout,
        quiet=args.quiet,
        skip_comparison=True,
        output_root_override=settings.output_root,
        output_directory_override=settings.output_directory,
        extension=collector,
    )
    summary = {
        **collector.summary(),
        "run_id": result.run_id,
        "energyplus_exit_code": result.exit_code,
        "runner_status": result.status.value,
        "output_validation_status": result.validation_status,
        "sensor_validation_status": "NOT_RUN",
        "baseline_comparison_status": "NOT_RUN",
        "model_sha256": result.model_sha256,
        "weather_sha256": result.weather_sha256,
        "actuator_access_count": 0,
    }
    summary_path = settings.output_directory / "sensor_extraction_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    checks, _ = validate_sensor_output(sensor_config)
    sensor_validation_ok = validation_exit_code(checks) == 0
    comparison_ok = True
    if not args.skip_baseline_comparison:
        comparison_code, _ = compare_sensor_run(
            (root / args.api_config).resolve()
            if not args.api_config.is_absolute()
            else args.api_config,
            settings.output_directory,
        )
        comparison_ok = comparison_code == 0
    summary["sensor_validation_status"] = "PASS" if sensor_validation_ok else "FAIL"
    summary["baseline_comparison_status"] = "PASS" if comparison_ok else "FAIL"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    counters = collector.counters
    print(f"Run ID: {result.run_id}")
    print(f"EnergyPlus exit code: {result.exit_code}")
    print(f"Total sensor callbacks: {counters.total_callback_invocations}")
    print(f"Successful snapshots: {counters.successful_snapshots}")
    print(f"Warmup calls skipped: {counters.warmup_calls_skipped}")
    print(f"Non-weather calls skipped: {counters.non_weather_environments_skipped}")
    print(f"Required handles ready: {collector.registry.required_ready}")
    print(f"Optional sensors unavailable: {counters.missing_optional_handles}")
    print(f"Sensor read errors: {counters.sensor_read_errors}")
    print(f"First timestamp: {counters.first_snapshot_time}")
    print(f"Last timestamp: {counters.last_snapshot_time}")
    print(f"JSONL: {settings.output_directory / settings.snapshots_jsonl}")
    print(f"CSV: {settings.output_directory / settings.snapshots_csv}")
    print(f"Sensor validation: {summary['sensor_validation_status']}")
    print(f"Baseline comparison: {summary['baseline_comparison_status']}")
    passed = (
        result.status is RunStatus.PASS
        and sensor_validation_ok
        and comparison_ok
        and not collector.callback_errors
    )
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
