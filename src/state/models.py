"""Immutable canonical Module 6 building-state models."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class StateValidationError(ValueError):
    """Base class for invalid canonical state."""


class InvalidRequiredFieldError(StateValidationError):
    pass


class MissingRequiredZoneError(StateValidationError):
    pass


class DuplicateZoneError(StateValidationError):
    pass


class NonFiniteValueError(StateValidationError):
    pass


class InvalidTimestampError(StateValidationError):
    pass


class NonMonotonicSequenceError(StateValidationError):
    pass


class UnsupportedSchemaVersionError(StateValidationError):
    pass


class ZoneClassification(StrEnum):
    OCCUPIED_CONDITIONED = "OCCUPIED_CONDITIONED"
    UNOCCUPIED_CONDITIONED = "UNOCCUPIED_CONDITIONED"
    PLENUM = "PLENUM"
    OTHER = "OTHER"


@dataclass(frozen=True)
class SensorAvailability:
    field: str
    available: bool
    source: str
    reason: str = ""


@dataclass(frozen=True)
class StateQualityIssue:
    code: str
    severity: str
    message: str
    zone_id: str | None = None


@dataclass(frozen=True)
class SimulationClock:
    environment_number: int
    environment_type: int
    calendar_year: int | None
    month: int
    day: int
    day_of_year: int
    day_of_week: int
    hour: int
    minute: int
    current_time_hours: float
    current_simulation_time_hours: float
    zone_timestep_number: int
    zone_timesteps_per_hour: int
    warmup: bool

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12 or not 1 <= self.day <= 31:
            raise InvalidTimestampError("Invalid month/day.")
        # EnergyPlus Runtime API minute values are preserved verbatim. The validated
        # Module 4 annual stream contains floating-point-derived values up to 68.
        if not 0 <= self.hour <= 24 or not 0 <= self.minute <= 99:
            raise InvalidTimestampError("Invalid simulation hour/minute.")
        if self.zone_timestep_number < 1 or self.zone_timesteps_per_hour < 1:
            raise InvalidTimestampError("Invalid zone timestep.")


@dataclass(frozen=True)
class OutdoorState:
    dry_bulb_c: float
    relative_humidity_percent: float
    availability: tuple[SensorAvailability, ...]


@dataclass(frozen=True)
class BuildingEnergyState:
    facility_purchased_electricity_raw_j: float
    facility_demand_rate_w: float
    hvac_electricity_raw_j: float
    cooling_electricity_raw_j: float | None
    heating_electricity_raw_j: float | None
    meter_units: str
    availability: tuple[SensorAvailability, ...]


@dataclass(frozen=True)
class ZoneState:
    exact_name: str
    zone_id: str
    classification: ZoneClassification
    occupancy_capable: bool
    is_plenum: bool
    mean_air_temperature_c: float
    occupant_count: float
    relative_humidity_percent: float | None
    pmv: float | None
    co2_ppm: float | None
    effective_cooling_setpoint_c: float | None
    availability: tuple[SensorAvailability, ...]
    quality_issues: tuple[StateQualityIssue, ...] = ()

    def __post_init__(self) -> None:
        if not math.isfinite(self.mean_air_temperature_c):
            raise NonFiniteValueError(f"Non-finite temperature for {self.exact_name}.")
        if not math.isfinite(self.occupant_count) or self.occupant_count < 0:
            raise InvalidRequiredFieldError(f"Invalid occupancy for {self.exact_name}.")
        if self.relative_humidity_percent is not None and not (
            math.isfinite(self.relative_humidity_percent)
            and 0 <= self.relative_humidity_percent <= 100
        ):
            raise InvalidRequiredFieldError(f"Invalid humidity for {self.exact_name}.")


@dataclass(frozen=True)
class BuildingState:
    schema_version: int
    run_id: str
    sequence: int
    source: str
    execution_mode: str
    captured_at_utc: str
    clock: SimulationClock
    outdoor: OutdoorState
    building_energy: BuildingEnergyState
    zones: tuple[ZoneState, ...]
    sensor_availability: tuple[SensorAvailability, ...]
    quality_issues: tuple[StateQualityIssue, ...]
    raw_snapshot_sequence: int
    fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise UnsupportedSchemaVersionError(str(self.schema_version))
        if not self.run_id or self.sequence < 1:
            raise InvalidRequiredFieldError("Run ID and positive sequence are required.")
        zone_ids = [zone.zone_id for zone in self.zones]
        if len(zone_ids) != len(set(zone_ids)):
            raise DuplicateZoneError("Duplicate canonical zone ID.")
        required = [
            self.outdoor.dry_bulb_c,
            self.outdoor.relative_humidity_percent,
            self.building_energy.facility_purchased_electricity_raw_j,
            self.building_energy.facility_demand_rate_w,
            self.building_energy.hvac_electricity_raw_j,
        ]
        if not all(math.isfinite(value) for value in required):
            raise NonFiniteValueError("A required building value is non-finite.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True)
class RunMetadata:
    run_id: str
    module: int
    execution_mode: str
    status: str
    started_at_utc: str
    energyplus_version: str
    api_version: str
    model_path: str
    model_checksum: str
    weather_path: str
    weather_checksum: str
    configuration_checksum: str
    expected_snapshot_count: int
    notes: str = ""


@dataclass(frozen=True)
class RunCompletion:
    run_id: str
    status: str
    finished_at_utc: str
    persisted_snapshot_count: int
    first_sequence: int
    last_sequence: int
    first_simulation_timestamp: str
    last_simulation_timestamp: str
    severe_count: int
    fatal_count: int
    callback_error_count: int
    api_error_count: int
    subscriber_error_count: int
    persistence_error_count: int
    queue_drained: bool
    actuator_access_count: int = 0
    control_decision_count: int = 0


def building_state_from_dict(raw: dict[str, Any]) -> BuildingState:
    """Rehydrate a canonical state from its persisted JSON representation."""
    clock = raw["clock"]
    outdoor = raw["outdoor"]
    energy = raw["building_energy"]

    def availability(items: list[dict[str, Any]]) -> tuple[SensorAvailability, ...]:
        return tuple(SensorAvailability(**item) for item in items)

    def issues(items: list[dict[str, Any]]) -> tuple[StateQualityIssue, ...]:
        return tuple(StateQualityIssue(**item) for item in items)

    zones = tuple(
        ZoneState(
            exact_name=item["exact_name"],
            zone_id=item["zone_id"],
            classification=ZoneClassification(item["classification"]),
            occupancy_capable=item["occupancy_capable"],
            is_plenum=item["is_plenum"],
            mean_air_temperature_c=item["mean_air_temperature_c"],
            occupant_count=item["occupant_count"],
            relative_humidity_percent=item["relative_humidity_percent"],
            pmv=item["pmv"],
            co2_ppm=item["co2_ppm"],
            effective_cooling_setpoint_c=item["effective_cooling_setpoint_c"],
            availability=availability(item["availability"]),
            quality_issues=issues(item["quality_issues"]),
        )
        for item in raw["zones"]
    )
    return BuildingState(
        schema_version=raw["schema_version"],
        run_id=raw["run_id"],
        sequence=raw["sequence"],
        source=raw["source"],
        execution_mode=raw["execution_mode"],
        captured_at_utc=raw["captured_at_utc"],
        clock=SimulationClock(**clock),
        outdoor=OutdoorState(
            outdoor["dry_bulb_c"],
            outdoor["relative_humidity_percent"],
            availability(outdoor["availability"]),
        ),
        building_energy=BuildingEnergyState(
            energy["facility_purchased_electricity_raw_j"],
            energy["facility_demand_rate_w"],
            energy["hvac_electricity_raw_j"],
            energy["cooling_electricity_raw_j"],
            energy["heating_electricity_raw_j"],
            energy["meter_units"],
            availability(energy["availability"]),
        ),
        zones=zones,
        sensor_availability=availability(raw["sensor_availability"]),
        quality_issues=issues(raw["quality_issues"]),
        raw_snapshot_sequence=raw["raw_snapshot_sequence"],
        fingerprint=raw["fingerprint"],
    )
