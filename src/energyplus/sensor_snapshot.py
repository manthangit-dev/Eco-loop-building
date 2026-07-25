"""Typed immutable snapshots of read-only EnergyPlus state."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SimulationTimestamp:
    environment_number: int
    environment_type: int
    year: int
    calendar_year: int
    month: int
    day: int
    day_of_year: int
    day_of_week: int
    hour: int
    minute: int
    current_time: float
    current_simulation_time: float
    zone_timestep_number: int
    timesteps_per_hour: int
    warmup: bool

    def identity(self) -> tuple[int, int, int, int, int]:
        return (
            self.environment_number,
            self.day_of_year,
            self.hour,
            self.minute,
            self.zone_timestep_number,
        )


@dataclass(frozen=True)
class ZoneSensorState:
    zone_name: str
    mean_air_temperature_c: float
    occupant_count: float
    relative_humidity_percent: float | None = None
    fanger_pmv: float | None = None
    co2_ppm: float | None = None


@dataclass(frozen=True)
class BuildingSensorState:
    facility_electricity_raw_j: float
    facility_demand_rate_w: float
    hvac_electricity_raw_j: float
    optional_meters_raw_j: dict[str, float | None] = field(default_factory=dict)


@dataclass(frozen=True)
class OutdoorSensorState:
    dry_bulb_c: float
    relative_humidity_percent: float


@dataclass(frozen=True)
class SensorSnapshot:
    sequence: int
    timestamp: SimulationTimestamp
    outdoor: OutdoorSensorState
    building: BuildingSensorState
    zones: tuple[ZoneSensorState, ...]
    sensor_errors: tuple[str, ...] = ()
    optional_availability: dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = [
            self.outdoor.dry_bulb_c,
            self.outdoor.relative_humidity_percent,
            self.building.facility_electricity_raw_j,
            self.building.facility_demand_rate_w,
            self.building.hvac_electricity_raw_j,
        ]
        required.extend(zone.mean_air_temperature_c for zone in self.zones)
        required.extend(zone.occupant_count for zone in self.zones)
        if not all(math.isfinite(value) for value in required):
            raise ValueError("Required sensor values must be finite.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False)


def csv_headers(zones: tuple[str, ...], optional_meter_ids: tuple[str, ...]) -> list[str]:
    headers = [
        "sequence",
        "environment_number",
        "environment_type",
        "year",
        "calendar_year",
        "month",
        "day",
        "day_of_year",
        "day_of_week",
        "hour",
        "minute",
        "current_time",
        "current_simulation_time",
        "zone_timestep_number",
        "timesteps_per_hour",
        "warmup",
        "outdoor_dry_bulb_c",
        "outdoor_relative_humidity_percent",
        "facility_electricity_raw_j",
        "facility_demand_rate_w",
        "hvac_electricity_raw_j",
    ]
    headers.extend(f"meter.{logical_id}.raw_j" for logical_id in optional_meter_ids)
    for zone in zones:
        headers.extend(
            [
                f"zone.{zone}.mean_air_temperature_c",
                f"zone.{zone}.occupant_count",
                f"zone.{zone}.relative_humidity_percent",
                f"zone.{zone}.fanger_pmv",
                f"zone.{zone}.co2_ppm",
            ]
        )
    return headers


def flatten_snapshot(
    snapshot: SensorSnapshot,
    zones: tuple[str, ...],
    optional_meter_ids: tuple[str, ...],
) -> dict[str, Any]:
    timestamp = snapshot.timestamp
    row: dict[str, Any] = {
        "sequence": snapshot.sequence,
        "environment_number": timestamp.environment_number,
        "environment_type": timestamp.environment_type,
        "year": timestamp.year,
        "calendar_year": timestamp.calendar_year,
        "month": timestamp.month,
        "day": timestamp.day,
        "day_of_year": timestamp.day_of_year,
        "day_of_week": timestamp.day_of_week,
        "hour": timestamp.hour,
        "minute": timestamp.minute,
        "current_time": timestamp.current_time,
        "current_simulation_time": timestamp.current_simulation_time,
        "zone_timestep_number": timestamp.zone_timestep_number,
        "timesteps_per_hour": timestamp.timesteps_per_hour,
        "warmup": timestamp.warmup,
        "outdoor_dry_bulb_c": snapshot.outdoor.dry_bulb_c,
        "outdoor_relative_humidity_percent": snapshot.outdoor.relative_humidity_percent,
        "facility_electricity_raw_j": snapshot.building.facility_electricity_raw_j,
        "facility_demand_rate_w": snapshot.building.facility_demand_rate_w,
        "hvac_electricity_raw_j": snapshot.building.hvac_electricity_raw_j,
    }
    for logical_id in optional_meter_ids:
        row[f"meter.{logical_id}.raw_j"] = snapshot.building.optional_meters_raw_j.get(logical_id)
    zone_map = {zone.zone_name: zone for zone in snapshot.zones}
    for zone_name in zones:
        zone = zone_map[zone_name]
        row[f"zone.{zone_name}.mean_air_temperature_c"] = zone.mean_air_temperature_c
        row[f"zone.{zone_name}.occupant_count"] = zone.occupant_count
        row[f"zone.{zone_name}.relative_humidity_percent"] = zone.relative_humidity_percent
        row[f"zone.{zone_name}.fanger_pmv"] = zone.fanger_pmv
        row[f"zone.{zone_name}.co2_ppm"] = zone.co2_ppm
    return row
