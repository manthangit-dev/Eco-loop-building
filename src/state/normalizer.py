"""Strict SensorSnapshot-to-BuildingState normalization."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.energyplus.sensor_snapshot import (
    BuildingSensorState,
    OutdoorSensorState,
    SensorSnapshot,
    SimulationTimestamp,
    ZoneSensorState,
)
from src.state.fingerprints import fingerprint_payload
from src.state.models import (
    BuildingEnergyState,
    BuildingState,
    DuplicateZoneError,
    MissingRequiredZoneError,
    NonMonotonicSequenceError,
    OutdoorState,
    SensorAvailability,
    SimulationClock,
    StateQualityIssue,
    ZoneState,
)
from src.state.zone_classification import ZoneEvidence


def snapshot_from_dict(raw: dict[str, Any]) -> SensorSnapshot:
    timestamp = raw["timestamp"]
    building = raw["building"]
    return SensorSnapshot(
        sequence=int(raw["sequence"]),
        timestamp=SimulationTimestamp(
            environment_number=int(timestamp["environment_number"]),
            environment_type=int(timestamp["environment_type"]),
            year=int(timestamp["year"]),
            calendar_year=int(timestamp["calendar_year"]),
            month=int(timestamp["month"]),
            day=int(timestamp["day"]),
            day_of_year=int(timestamp["day_of_year"]),
            day_of_week=int(timestamp["day_of_week"]),
            hour=int(timestamp["hour"]),
            minute=int(timestamp["minute"]),
            current_time=float(timestamp["current_time"]),
            current_simulation_time=float(timestamp["current_simulation_time"]),
            zone_timestep_number=int(timestamp["zone_timestep_number"]),
            timesteps_per_hour=int(timestamp["timesteps_per_hour"]),
            warmup=bool(timestamp["warmup"]),
        ),
        outdoor=OutdoorSensorState(
            dry_bulb_c=float(raw["outdoor"]["dry_bulb_c"]),
            relative_humidity_percent=float(raw["outdoor"]["relative_humidity_percent"]),
        ),
        building=BuildingSensorState(
            facility_electricity_raw_j=float(building["facility_electricity_raw_j"]),
            facility_demand_rate_w=float(building["facility_demand_rate_w"]),
            hvac_electricity_raw_j=float(building["hvac_electricity_raw_j"]),
            optional_meters_raw_j={
                str(key): None if value is None else float(value)
                for key, value in building.get("optional_meters_raw_j", {}).items()
            },
        ),
        zones=tuple(
            ZoneSensorState(
                zone_name=str(zone["zone_name"]),
                mean_air_temperature_c=float(zone["mean_air_temperature_c"]),
                occupant_count=float(zone["occupant_count"]),
                relative_humidity_percent=(
                    None
                    if zone.get("relative_humidity_percent") is None
                    else float(zone["relative_humidity_percent"])
                ),
                fanger_pmv=(None if zone.get("fanger_pmv") is None else float(zone["fanger_pmv"])),
                co2_ppm=None if zone.get("co2_ppm") is None else float(zone["co2_ppm"]),
            )
            for zone in raw["zones"]
        ),
        sensor_errors=tuple(str(item) for item in raw.get("sensor_errors", [])),
        optional_availability={
            str(key): bool(value) for key, value in raw.get("optional_availability", {}).items()
        },
    )


class StateNormalizer:
    def __init__(
        self,
        run_id: str,
        execution_mode: str,
        zone_evidence: tuple[ZoneEvidence, ...],
    ) -> None:
        self.run_id = run_id
        self.execution_mode = execution_mode
        self.zone_evidence = zone_evidence
        self._last_sequence = 0

    @staticmethod
    def _availability(field: str, value: object, source: str) -> SensorAvailability:
        return SensorAvailability(
            field=field,
            available=value is not None,
            source=source,
            reason="" if value is not None else "Not available in source snapshot.",
        )

    def normalize(self, snapshot: SensorSnapshot) -> BuildingState:
        if snapshot.sequence <= self._last_sequence:
            raise NonMonotonicSequenceError(
                f"Sequence {snapshot.sequence} follows {self._last_sequence}."
            )
        source_zones = {zone.zone_name: zone for zone in snapshot.zones}
        if len(source_zones) != len(snapshot.zones):
            raise DuplicateZoneError("Duplicate exact zone name in snapshot.")
        expected = {item.exact_name for item in self.zone_evidence}
        missing = expected - set(source_zones)
        if missing:
            raise MissingRequiredZoneError(f"Missing zones: {sorted(missing)}")
        zones: list[ZoneState] = []
        for evidence in self.zone_evidence:
            source = source_zones[evidence.exact_name]
            availability = (
                self._availability(
                    "relative_humidity_percent",
                    source.relative_humidity_percent,
                    "EnergyPlus",
                ),
                self._availability("pmv", source.fanger_pmv, "EnergyPlus"),
                self._availability("co2_ppm", source.co2_ppm, "EnergyPlus"),
                self._availability("effective_cooling_setpoint_c", None, "EnergyPlus"),
            )
            zones.append(
                ZoneState(
                    exact_name=evidence.exact_name,
                    zone_id=evidence.zone_id,
                    classification=evidence.classification,
                    occupancy_capable=evidence.occupancy_capable,
                    is_plenum=evidence.is_plenum,
                    mean_air_temperature_c=source.mean_air_temperature_c,
                    occupant_count=source.occupant_count,
                    relative_humidity_percent=source.relative_humidity_percent,
                    pmv=source.fanger_pmv,
                    co2_ppm=source.co2_ppm,
                    effective_cooling_setpoint_c=None,
                    availability=availability,
                )
            )
        timestamp = snapshot.timestamp
        optional = snapshot.building.optional_meters_raw_j
        building_availability = tuple(
            SensorAvailability(
                field=key,
                available=bool(value),
                source="EnergyPlus",
                reason="" if value else "Optional handle unavailable.",
            )
            for key, value in sorted(snapshot.optional_availability.items())
        )
        issues = tuple(
            StateQualityIssue("SOURCE_SENSOR_ERROR", "WARN", message)
            for message in snapshot.sensor_errors
        )
        payload = snapshot.to_dict()
        state = BuildingState(
            schema_version=1,
            run_id=self.run_id,
            sequence=snapshot.sequence,
            source="EnergyPlus",
            execution_mode=self.execution_mode,
            captured_at_utc=datetime.now(UTC).isoformat(),
            clock=SimulationClock(
                environment_number=timestamp.environment_number,
                environment_type=timestamp.environment_type,
                calendar_year=timestamp.calendar_year or None,
                month=timestamp.month,
                day=timestamp.day,
                day_of_year=timestamp.day_of_year,
                day_of_week=timestamp.day_of_week,
                hour=timestamp.hour,
                minute=timestamp.minute,
                current_time_hours=timestamp.current_time,
                current_simulation_time_hours=timestamp.current_simulation_time,
                zone_timestep_number=timestamp.zone_timestep_number,
                zone_timesteps_per_hour=timestamp.timesteps_per_hour,
                warmup=timestamp.warmup,
            ),
            outdoor=OutdoorState(
                snapshot.outdoor.dry_bulb_c,
                snapshot.outdoor.relative_humidity_percent,
                (
                    self._availability("dry_bulb_c", snapshot.outdoor.dry_bulb_c, "EnergyPlus"),
                    self._availability(
                        "relative_humidity_percent",
                        snapshot.outdoor.relative_humidity_percent,
                        "EnergyPlus",
                    ),
                ),
            ),
            building_energy=BuildingEnergyState(
                facility_purchased_electricity_raw_j=(snapshot.building.facility_electricity_raw_j),
                facility_demand_rate_w=snapshot.building.facility_demand_rate_w,
                hvac_electricity_raw_j=snapshot.building.hvac_electricity_raw_j,
                cooling_electricity_raw_j=optional.get("cooling_electricity"),
                heating_electricity_raw_j=optional.get("heating_electricity"),
                meter_units="J",
                availability=building_availability,
            ),
            zones=tuple(zones),
            sensor_availability=building_availability,
            quality_issues=issues,
            raw_snapshot_sequence=snapshot.sequence,
            fingerprint=fingerprint_payload(payload),
        )
        self._last_sequence = snapshot.sequence
        return state
