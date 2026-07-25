"""Independently validate persisted Module 5 control/intervention outputs."""

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

from src.energyplus.actuator_definitions import load_actuator_settings  # noqa: E402
from src.energyplus.actuator_plan import WindowPosition, build_plan  # noqa: E402

from scripts.validate_baseline import (  # noqa: E402
    Check,
    Status,
    parse_error_summary,
    validation_exit_code,
)


def _check(name: str, condition: bool, detail: str) -> Check:
    return Check(name, Status.PASS if condition else Status.FAIL, detail)


def _events(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def validate(config: Path, run_type: str = "both") -> tuple[list[Check], Path]:
    root = config.resolve().parents[1]
    settings = load_actuator_settings(config, root)
    plan = build_plan(settings)
    checks: list[Check] = []
    selected: tuple[tuple[str, Path], ...] = (
        ("control", settings.control_output),
        ("intervention", settings.intervention_output),
    )
    if run_type != "both":
        selected = tuple(item for item in selected if item[0] == run_type)
    summaries: dict[str, dict[str, Any]] = {}
    event_sets: dict[str, list[dict[str, Any]]] = {}
    for name, output in selected:
        checks.append(_check(f"{name} output", output.is_dir(), str(output)))
        required = [
            "run_metadata.json",
            settings.summary_json,
            settings.manifest_json,
            settings.event_jsonl,
            "sensor_snapshots.jsonl",
            "sensor_snapshots.csv",
            "sensor_manifest.json",
            "thermoledger.err",
        ]
        checks.append(
            _check(
                f"{name} required files",
                all(
                    (output / item).is_file() and (output / item).stat().st_size > 0
                    for item in required
                ),
                ", ".join(required),
            )
        )
        if checks[-1].status is Status.FAIL:
            continue
        summary = json.loads((output / settings.summary_json).read_text())
        manifest = json.loads((output / settings.manifest_json).read_text())
        events = _events(output / settings.event_jsonl)
        summaries[name], event_sets[name] = summary, events
        errors = parse_error_summary((output / "thermoledger.err").read_text(errors="replace"))
        writes = [
            event
            for event in events
            if event["event_type"] in {"OVERRIDE_APPLIED", "OVERRIDE_REAPPLIED"}
        ]
        resets = [event for event in events if event["event_type"] == "OVERRIDE_RESET"]
        outside = []
        unsafe = []
        unapproved = []
        for event in writes:
            month_day, time = event["simulation_timestamp"].split()
            month, day = map(int, month_day.split("-"))
            hour, minute = map(int, time.split(":"))
            if plan.position(month, day, hour, minute) is not WindowPosition.DURING:
                outside.append(event)
            value = float(event["approved_setpoint"])
            if (
                not math.isfinite(value)
                or not plan.actuator.minimum <= value <= plan.actuator.maximum
            ):
                unsafe.append(event)
            if (
                event["component_type"],
                event["control_type"],
                event["key"],
            ) != (
                plan.actuator.component_type,
                plan.actuator.control_type,
                plan.actuator.unique_key,
            ):
                unapproved.append(event)
        checks.extend(
            [
                _check(
                    f"{name} exit",
                    summary.get("energyplus_exit_code") == 0,
                    str(summary.get("energyplus_exit_code")),
                ),
                _check(
                    f"{name} severe/fatal",
                    errors.severe == errors.fatal == 0,
                    f"{errors.severe}/{errors.fatal}",
                ),
                _check(
                    f"{name} snapshots",
                    summary.get("sensor_snapshot_count") == 35040,
                    str(summary.get("sensor_snapshot_count")),
                ),
                _check(
                    f"{name} handle",
                    isinstance(summary.get("handle"), int) and summary["handle"] != -1,
                    str(summary.get("handle")),
                ),
                _check(
                    f"{name} approved actuator",
                    manifest.get("approved_actuator_count") == 1,
                    str(manifest.get("approved_actuator_count")),
                ),
                _check(
                    f"{name} callback/API errors",
                    summary.get("callback_error_count") == 0
                    and summary.get("api_error_activations") == 0
                    and summary.get("registry_api_error_count") == 0,
                    "must all be zero",
                ),
                _check(
                    f"{name} safe writes",
                    not outside and not unsafe and not unapproved,
                    f"outside={len(outside)}, unsafe={len(unsafe)}, unapproved={len(unapproved)}",
                ),
            ]
        )
        if name == "control":
            checks.append(
                _check(
                    "Control has zero writes",
                    not writes and summary.get("set_calls") == 0,
                    str(len(writes)),
                )
            )
        else:
            observations = [event for event in events if event["effective_setpoint"] is not None]
            during: list[dict[str, Any]] = []
            after: list[dict[str, Any]] = []
            for event in observations:
                date, time = event["simulation_timestamp"].split()
                month, day = map(int, date.split("-"))
                hour, minute = map(int, time.split(":"))
                position = plan.position(month, day, hour, minute)
                (
                    during
                    if position is WindowPosition.DURING
                    else after
                    if position is WindowPosition.AFTER
                    else []
                ).append(event)
            tolerance = float(settings.raw["validation"]["setpoint_tolerance_celsius"])
            recovery = float(settings.raw["validation"]["recovery_tolerance_celsius"])
            checks.extend(
                [
                    _check(
                        "Intervention has writes",
                        bool(writes) and summary.get("set_calls", 0) > 0,
                        str(len(writes)),
                    ),
                    _check(
                        "Intervention has reset",
                        bool(resets) and summary.get("reset_calls", 0) > 0,
                        str(len(resets)),
                    ),
                    _check(
                        "Effective set-point response",
                        any(
                            abs(float(e["effective_setpoint"]) - plan.approved_setpoint)
                            <= tolerance
                            for e in during
                        ),
                        f"target={plan.approved_setpoint}",
                    ),
                    _check(
                        "Post-reset recovery",
                        any(
                            abs(float(e["effective_setpoint"]) - plan.baseline_setpoint) <= recovery
                            for e in after[:8]
                        ),
                        f"baseline={plan.baseline_setpoint}",
                    ),
                ]
            )
    manifest = json.loads((root / "models/MODEL_MANIFEST.json").read_text())
    import hashlib

    files = [
        (
            root / "models/source/5ZoneAirCooled_v26_1_original.idf",
            manifest["repository_source_copy_sha256"],
            "source",
        ),
        (
            root / "models/baseline/thermoledger_5zone_baseline.idf",
            manifest["derived_baseline_sha256"],
            "baseline",
        ),
        (
            root / "weather/input" / manifest["weather_filename"],
            manifest["weather_sha256"],
            "weather",
        ),
    ]
    for path, expected, name in files:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        checks.append(_check(f"{name} checksum", actual == expected, actual))
    output = settings.output_root / settings.validation_json
    output.write_text(
        json.dumps(
            {
                "status": "PASS" if validation_exit_code(checks) == 0 else "FAIL",
                "checks": [asdict(item) for item in checks],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return checks, output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actuator-config", type=Path, default=Path("config/actuators.yaml"))
    parser.add_argument("--run-type", choices=("control", "intervention", "both"), default="both")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    config = (
        args.actuator_config if args.actuator_config.is_absolute() else root / args.actuator_config
    )
    checks, output = validate(config, args.run_type)
    for item in checks:
        print(f"[{item.status.value}] {item.name}: {item.detail}")
    print(f"Validation summary: {output}")
    return validation_exit_code(checks)


if __name__ == "__main__":
    raise SystemExit(main())
