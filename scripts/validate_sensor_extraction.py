"""Validate completed Module 4 read-only sensor extraction outputs."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.energyplus.sensor_definitions import load_sensor_settings  # noqa: E402

from scripts.validate_baseline import (  # noqa: E402
    Check,
    Status,
    check_checksum,
    check_file,
    parse_error_summary,
    validation_exit_code,
)


def _check(name: str, condition: bool, detail: str) -> Check:
    return Check(name, Status.PASS if condition else Status.FAIL, detail)


def validate_sensor_output(
    sensor_config: Path,
    output_override: Path | None = None,
) -> tuple[list[Check], Path]:
    root = sensor_config.resolve().parents[1]
    settings = load_sensor_settings(sensor_config, root)
    output = output_override or settings.output_directory
    checks: list[Check] = []
    try:
        output.resolve().relative_to(settings.output_root)
        safe = output.resolve() != settings.output_root
    except ValueError:
        safe = False
    checks.append(_check("Output safety", safe, f"Output: {output}"))
    if not output.is_dir():
        checks.append(Check("Output directory", Status.FAIL, f"Missing: {output}"))
        return checks, output

    metadata_path = output / "run_metadata.json"
    manifest_path = output / settings.manifest_json
    summary_path = output / "sensor_extraction_summary.json"
    jsonl_path = output / settings.snapshots_jsonl
    csv_path = output / settings.snapshots_csv
    discovery_path = output / settings.discovery_csv
    error_path = output / "thermoledger.err"
    for path, name in (
        (metadata_path, "Run metadata"),
        (manifest_path, "Sensor manifest"),
        (summary_path, "Extraction summary"),
        (jsonl_path, "Sensor JSONL"),
        (csv_path, "Sensor CSV"),
        (discovery_path, "Available API data"),
        (error_path, "EnergyPlus error file"),
    ):
        checks.append(check_file(path, name))
    if any(check.status is Status.FAIL for check in checks):
        return checks, output

    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    sensor_manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    extraction = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    counts = parse_error_summary(
        error_path.read_text(encoding="utf-8", errors="replace")
    )
    checks.extend(
        [
            _check(
                "EnergyPlus exit code",
                metadata.get("exit_code") == 0,
                str(metadata.get("exit_code")),
            ),
            _check("Severe errors", counts.severe == 0, str(counts.severe)),
            _check("Fatal errors", counts.fatal == 0, str(counts.fatal)),
            _check(
                "Required handles",
                bool(sensor_manifest.get("required_handles_ready")),
                str(sensor_manifest.get("required_handles_ready")),
            ),
            _check(
                "Callback errors",
                extraction.get("callback_error_count") == 0,
                str(extraction.get("callback_error_count")),
            ),
            _check(
                "API errors",
                extraction.get("registry_api_error_count") == 0,
                str(extraction.get("registry_api_error_count")),
            ),
            _check(
                "No actuator access",
                extraction.get("actuator_access_count") == 0
                and sensor_manifest.get("actuator_access_count") == 0,
                "Recorded actuator access must be zero.",
            ),
        ]
    )

    identities: set[tuple[int, int, int, int, int]] = set()
    zones_seen: set[str] = set()
    row_count = 0
    last_time: float | None = None
    data_errors: list[str] = []
    with jsonl_path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            row_count += 1
            row: dict[str, Any] = json.loads(line)
            timestamp = row["timestamp"]
            identity = (
                int(timestamp["environment_number"]),
                int(timestamp["day_of_year"]),
                int(timestamp["hour"]),
                int(timestamp["minute"]),
                int(timestamp["zone_timestep_number"]),
            )
            if identity in identities:
                data_errors.append(f"duplicate identity at line {line_number}")
            identities.add(identity)
            current = float(timestamp["current_simulation_time"])
            if last_time is not None and current < last_time:
                data_errors.append(f"non-monotonic time at line {line_number}")
            last_time = current
            if timestamp["warmup"]:
                data_errors.append(f"warmup row at line {line_number}")
            if int(timestamp["environment_type"]) != settings.weather_run_environment_type:
                data_errors.append(f"unapproved environment at line {line_number}")
            if not 1 <= int(timestamp["zone_timestep_number"]) <= int(
                timestamp["timesteps_per_hour"]
            ):
                data_errors.append(f"invalid timestep at line {line_number}")
            required_values = [
                row["outdoor"]["dry_bulb_c"],
                row["outdoor"]["relative_humidity_percent"],
                row["building"]["facility_electricity_raw_j"],
                row["building"]["facility_demand_rate_w"],
                row["building"]["hvac_electricity_raw_j"],
            ]
            for zone in row["zones"]:
                zones_seen.add(str(zone["zone_name"]))
                required_values.extend(
                    [zone["mean_air_temperature_c"], zone["occupant_count"]]
                )
                if float(zone["occupant_count"]) < 0:
                    data_errors.append(f"negative occupancy at line {line_number}")
                humidity = zone.get("relative_humidity_percent")
                if humidity is not None and not 0 <= float(humidity) <= 100:
                    data_errors.append(f"invalid humidity at line {line_number}")
            if not all(math.isfinite(float(value)) for value in required_values):
                data_errors.append(f"non-finite required value at line {line_number}")
    checks.extend(
        [
            _check(
                "Minimum snapshots",
                row_count >= settings.minimum_snapshots,
                f"{row_count} snapshots; minimum {settings.minimum_snapshots}",
            ),
            _check(
                "All zones",
                zones_seen == set(settings.zones),
                f"Zones: {sorted(zones_seen)}",
            ),
            _check("Dataset integrity", not data_errors, "; ".join(data_errors[:10])),
        ]
    )

    project_manifest = json.loads(
        (root / "models/MODEL_MANIFEST.json").read_text(encoding="utf-8")
    )
    checks.extend(
        [
            check_checksum(
                root / "models/source/5ZoneAirCooled_v26_1_original.idf",
                project_manifest["repository_source_copy_sha256"],
                "Source checksum",
            ),
            check_checksum(
                root / "models/baseline/thermoledger_5zone_baseline.idf",
                project_manifest["derived_baseline_sha256"],
                "Baseline checksum",
            ),
            check_checksum(
                root / "weather/input" / project_manifest["weather_filename"],
                project_manifest["weather_sha256"],
                "Weather checksum",
            ),
        ]
    )
    optional_missing = [
        item["logical_id"]
        for item in sensor_manifest["discoveries"]
        if not item["required"] and not item["available"]
    ]
    if optional_missing:
        checks.append(
            Check(
                "Optional sensors",
                Status.WARN,
                f"Unavailable optional sensors: {optional_missing}",
            )
        )
    payload = {
        "status": "PASS" if validation_exit_code(checks) == 0 else "FAIL",
        "snapshot_count": row_count,
        "checks": [asdict(check) for check in checks],
    }
    (output / settings.validation_json).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return checks, output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sensor-config", type=Path, default=Path("config/sensors.yaml"))
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args(argv)
    checks, output = validate_sensor_output(args.sensor_config, args.output_directory)
    for check in checks:
        print(f"[{check.status.value}] {check.name}: {check.detail}")
    print(f"Sensor output: {output}")
    return validation_exit_code(checks)


if __name__ == "__main__":
    raise SystemExit(main())
