"""Classify actuators from the persisted real Module 4 Runtime API catalog."""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.energyplus.actuator_definitions import load_actuator_settings  # noqa: E402


def discover(config: Path, source: Path | None = None) -> tuple[int, int, Path]:
    root = config.resolve().parents[1]
    settings = load_actuator_settings(config, root)
    catalog = (
        source or root / "data/output/module_4_sensor_extraction/current/available_api_data.csv"
    )
    lines = catalog.read_text(encoding="utf-8-sig").splitlines()
    records: list[dict[str, object]] = []
    zones = {"SPACE1-1", "SPACE2-1", "SPACE3-1", "SPACE4-1", "SPACE5-1"}
    for line in lines[1:]:
        if line.startswith("**"):
            break
        if not line:
            continue
        row = next(csv.reader([line]))
        if len(row) < 5 or row[0] != "Actuator":
            continue
        component, control, key, units = row[1:5]
        eligible = (
            component == "Zone Temperature Control"
            and control == "Cooling Setpoint"
            and key in zones
        )
        records.append(
            {
                "what": "Actuator",
                "component_type": component,
                "control_type": control,
                "unique_key": key,
                "units": units,
                "source": "Module 4 real Runtime API catalog",
                "occupied_zone": key in zones,
                "zone_count": 1 if component == "Zone Temperature Control" else 0,
                "eligible": eligible,
                "rejection_reason": (
                    "" if eligible else "Not an isolated occupied-zone cooling set-point."
                ),
            }
        )
    settings.output_root.mkdir(parents=True, exist_ok=True)
    output = settings.output_root / settings.discovery_csv
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    eligible_records = [item for item in records if item["eligible"]]
    print(f"Discovered actuators: {len(records)}")
    print(f"Eligible isolated cooling actuators: {len(eligible_records)}")
    for item in eligible_records:
        print(
            f"ELIGIBLE: {item['component_type']} / {item['control_type']} / "
            f"{item['unique_key']} / {item['units']}"
        )
    print(f"Discovery output: {output}")
    return len(records), len(eligible_records), output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actuator-config", type=Path, default=Path("config/actuators.yaml"))
    parser.add_argument("--source-catalog", type=Path)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    config = (
        args.actuator_config if args.actuator_config.is_absolute() else root / args.actuator_config
    )
    source = args.source_catalog
    if source is not None and not source.is_absolute():
        source = root / source
    _, eligible, _ = discover(config, source)
    return 0 if eligible else 1


if __name__ == "__main__":
    raise SystemExit(main())
