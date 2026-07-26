"""Strict local scenario loaders; recorded future telemetry is forbidden."""

import csv
import hashlib
from pathlib import Path

from src.planning.models import BuildingEvent, ForecastPoint


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_points(path: Path, kind: str, environment_id: str, zone: str) -> tuple[ForecastPoint, ...]:
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    points: list[ForecastPoint] = []
    value_key = {"weather": "outdoor_dry_bulb_c", "occupancy": "expected_occupancy"}.get(
        kind, "value"
    )
    for sequence, row in enumerate(rows):
        if row["environment_id"] != environment_id:
            continue
        row_zone = row.get("zone") or None
        if row_zone is not None and row_zone != zone:
            continue
        source = row["source"]
        if any(
            term in source.lower()
            for term in ("future telemetry", "controller outcome", "experimental output")
        ):
            raise ValueError("prohibited_future_source")
        points.append(
            ForecastPoint(
                forecast_type=kind.upper(),
                sequence=sequence,
                simulation_timestamp=row["simulation_timestamp"],
                zone=row_zone,
                value=float(row[value_key]),
                units=row["units"],
                uncertainty=row["uncertainty"],
                source=source,
                provenance={
                    "scenario_id": row["scenario_id"],
                    "schema_version": int(row["schema_version"]),
                    "checksum": checksum(path),
                },
            )
        )
    timestamps = [point.simulation_timestamp for point in points]
    if timestamps != sorted(timestamps) or len(timestamps) != len(set(timestamps)):
        raise ValueError("forecast timestamps must be unique and monotonic")
    return tuple(points)


def load_events(path: Path, environment_id: str, zone: str) -> tuple[BuildingEvent, ...]:
    events = []
    for row in csv.DictReader(path.open(encoding="utf-8", newline="")):
        if row["environment_id"] == environment_id and row["zone"] == zone:
            events.append(
                BuildingEvent(
                    start_timestamp=row["start_timestamp"],
                    end_timestamp=row["end_timestamp"],
                    zone=zone,
                    event_type=row["event_type"],
                    priority=row["priority"],
                    comfort_protection=row["comfort_protection"].lower() == "true",
                    source=row["source"],
                    uncertainty=row["uncertainty"],
                )
            )
    return tuple(events)
