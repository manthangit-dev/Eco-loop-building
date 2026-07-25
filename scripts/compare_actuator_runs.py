"""Compare Module 4, Module 5 control, and Module 5 intervention evidence."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.energyplus.actuator_definitions import load_actuator_settings  # noqa: E402
from src.energyplus.actuator_plan import WindowPosition, build_plan  # noqa: E402


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _sensor_diagnostics(path: Path, plan: Any) -> dict[str, float]:
    temperatures: list[float] = []
    facility: list[float] = []
    hvac: list[float] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            timestamp = row["timestamp"]
            position = plan.position(
                int(timestamp["month"]),
                int(timestamp["day"]),
                int(timestamp["hour"]),
                int(timestamp["minute"]),
            )
            if position is not WindowPosition.DURING:
                continue
            zone = next(item for item in row["zones"] if item["zone_name"] == plan.target_zone)
            temperatures.append(float(zone["mean_air_temperature_c"]))
            facility.append(float(row["building"]["facility_electricity_raw_j"]))
            hvac.append(float(row["building"]["hvac_electricity_raw_j"]))

    def mean(values: list[float]) -> float:
        return sum(values) / len(values)

    return {
        "target_zone_mean_temperature_c": mean(temperatures),
        "facility_interval_energy_mean_j": mean(facility),
        "hvac_interval_energy_mean_j": mean(hvac),
    }


def compare(config: Path) -> tuple[bool, Path]:
    root = config.resolve().parents[1]
    settings = load_actuator_settings(config, root)
    plan = build_plan(settings)
    control_summary = json.loads((settings.control_output / settings.summary_json).read_text())
    intervention_summary = json.loads(
        (settings.intervention_output / settings.summary_json).read_text()
    )
    control_events = _rows(settings.control_output / settings.event_jsonl)
    intervention_events = _rows(settings.intervention_output / settings.event_jsonl)

    def observations(events: list[dict[str, Any]], position: WindowPosition) -> list[float]:
        values = []
        for event in events:
            if event["effective_setpoint"] is None:
                continue
            date, time = event["simulation_timestamp"].split()
            month, day = map(int, date.split("-"))
            hour, minute = map(int, time.split(":"))
            if plan.position(month, day, hour, minute) is position:
                values.append(float(event["effective_setpoint"]))
        return values

    control_during = observations(control_events, WindowPosition.DURING)
    intervention_during = observations(intervention_events, WindowPosition.DURING)
    intervention_after = observations(intervention_events, WindowPosition.AFTER)[:8]
    control_diagnostics = _sensor_diagnostics(
        settings.control_output / "sensor_snapshots.jsonl", plan
    )
    intervention_diagnostics = _sensor_diagnostics(
        settings.intervention_output / "sensor_snapshots.jsonl", plan
    )
    checks = {
        "same_model": control_summary["model_sha256"] == intervention_summary["model_sha256"],
        "same_weather": control_summary["weather_sha256"] == intervention_summary["weather_sha256"],
        "complete_snapshots": control_summary["sensor_snapshot_count"]
        == intervention_summary["sensor_snapshot_count"]
        == 35040,
        "control_zero_writes": control_summary["set_calls"] == 0,
        "intervention_writes": intervention_summary["set_calls"] > 0,
        "setpoint_divergence": bool(control_during and intervention_during)
        and max(intervention_during) > max(control_during) + 0.5,
        "post_reset_convergence": any(
            abs(value - plan.baseline_setpoint) <= 0.25 for value in intervention_after
        ),
        "non_target_direct_overrides": intervention_summary["unapproved_actuator_write_count"] == 0,
        "zero_errors": control_summary["callback_error_count"]
        == intervention_summary["callback_error_count"]
        == 0,
    }
    payload = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "purpose": "actuator functionality; electricity differences are diagnostic only",
        "checks": checks,
        "control_during_setpoints": control_during,
        "intervention_during_setpoints": intervention_during,
        "intervention_post_reset_setpoints": intervention_after,
        "control_window_diagnostics": control_diagnostics,
        "intervention_window_diagnostics": intervention_diagnostics,
        "diagnostic_difference": {
            key: intervention_diagnostics[key] - control_diagnostics[key]
            for key in control_diagnostics
        },
    }
    output = settings.output_root / settings.comparison_json
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return all(checks.values()), output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actuator-config", type=Path, default=Path("config/actuators.yaml"))
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    config = (
        args.actuator_config if args.actuator_config.is_absolute() else root / args.actuator_config
    )
    passed, output = compare(config)
    print(f"Actuator comparison: {'PASS' if passed else 'FAIL'}")
    print(f"Comparison summary: {output}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
